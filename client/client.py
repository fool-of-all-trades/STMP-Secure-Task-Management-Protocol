import asyncio
import logging

from client.network.connection import ConnectionManager
from client.network.protocol import MsgType, build_frame, extract_request_id
from client.network.session_manager import STMPSessionManager, SessionState
from client.api.task_api import TaskAPI
from shared.error_codes import ERROR_CODES

logger = logging.getLogger("client")


class STMPClient(TaskAPI):
    def __init__(self, host: str = "127.0.0.1", port: int = 8888):
        self.host = host
        self.port = port

        self.connection = ConnectionManager()
        self.session = STMPSessionManager(self)

        self.connection.on_unexpected_disconnect = self._on_unexpected_disconnect

    # Właściwości pomocnicze
    @property
    def is_connected(self) -> bool:
        return self.connection.is_connected

    @is_connected.setter
    def is_connected(self, value: bool):
        self.connection.is_connected = value

    @property
    def session_token(self) -> str | None:
        return self.session.session_token

    # Zestawienie połączenia TLS
    async def connect(self) -> bool:
        if self.is_connected:
            return True

        ctx = ConnectionManager.create_ssl_context()
        try:
            logger.info("Łączenie z %s:%d przez TLS 1.3...", self.host, self.port)
            self.connection.reader, self.connection.writer = (
                await asyncio.open_connection(self.host, self.port, ssl=ctx)
            )
            self.connection.is_connected = True
            self.connection.update_activity()
            await self.connection.start_listen_loop()

            resp = await self.request(MsgType.HELLO, {"message": "Hello from GUI Client"})
            if resp.get("type") != MsgType.HELLO_OK:
                logger.error("Serwer odrzucił handshake: %s", resp)
                await self.disconnect()
                return False

            logger.info("Handshake zakończony: HELLO_OK odebrano.")
            self.session.update_state(SessionState.CONNECTED)
            await self.connection.start_keep_alive_loop(
                lambda: self.request(MsgType.PING, {})
            )
            return True

        except Exception as e:
            logger.error("Błąd połączenia: %s", e)
            self.connection.is_connected = False
            return False

    # Wylogowanie użytkownika i zamknięcie połączenia
    async def disconnect(self):
        self.session.clear_session()

        if self.connection._ping_task:
            self.connection._ping_task.cancel()
        if self.connection._listen_task:
            self.connection._listen_task.cancel()

        if self.is_connected and self.connection.writer:
            try:
                await asyncio.wait_for(self.request(MsgType.BYE, {}), timeout=1.5)
            except Exception:
                pass

        await self.connection.close_sockets()

    # Żądanie (do stanu sesji)
    async def request(self, msg_type: str, payload: dict, timeout: float = 5.0) -> dict:
        frame = build_frame(msg_type, payload, self.session.session_token)
        request_id = extract_request_id(frame)

        response = await self.connection.send_frame(frame, request_id, timeout)
        logger.debug(response.get("type", "?"))

        # Aktualizacja stanu sesji na podstawie odpowiedzi
        if response.get("type") == MsgType.LOGIN_OK:
            self.session.store_session(response["payload"])
        elif response.get("type") == MsgType.BYE:
            self.session.clear_session()

        return response

    # Pobranie tekstu na podstawie kodu błędu
    def _resolve_error(self, resp: dict, fallback: str) -> str:
        payload = resp.get("payload", {})
        error_code = payload.get("error_code")
        if error_code in ERROR_CODES:
            return f"{ERROR_CODES[error_code]}: {payload.get('message', fallback)}"
        return payload.get("message", fallback)

    # Obsługa logowania użytkownika
    async def login(self, username: str, password: str) -> dict:
        try:
            await self.request(MsgType.HELLO, {"message": "Login intent"})
            resp = await self.request("LOGIN", {"username": username, "password": password})
            if resp.get("type") == "LOGIN_OK":
                return {"success": True, "username": username}

            # Mapowanie błędów autentykacji
            return {"success": False, "message": self._resolve_error(resp, "Login failed.")}
        except Exception as e:
            return {"success": False, "message": f"Network error: {str(e)}"}

    # Obsługa rejestracji użytkownika
    async def register(self, username: str, password: str) -> dict:
        try:
            resp = await self.request("REGISTER", {"username": username, "password": password})
            if resp.get("type") == "REGISTER_OK":
                return {"success": True}

            # Mapowanie błędów rejestracji
            return {"success": False, "message": self._resolve_error(resp, "Registration failed.")}
        except Exception as e:
            return {"success": False, "message": f"Network error: {str(e)}"}

    # Obsługa ponownego logowania
    async def reauthenticate(self, username: str, password: str) -> dict:
        try:
            connected = await self.connect()
            if not connected:
                return {"success": False, "message": "Could not reconnect to server."}

            resp = await self.request("LOGIN", {"username": username, "password": password})
            if resp.get("type") == "LOGIN_OK":
                return {"success": True}

            # Mapowanie błędów reautentykacji
            return {"success": False, "message": self._resolve_error(resp, "Login failed.")}
        except Exception as e:
            return {"success": False, "message": f"Network error: {str(e)}"}

    # Pobranie listy zadań
    async def fetch_tasks(self) -> dict:
        try:
            resp = await self.request("GET_TASK", {})
            if resp.get("type") == "TASK_LIST":
                tasks = resp.get("payload", {}).get("tasks", [])
                return {"success": True, "tasks": tasks}

            # Mapowanie błędów pobierania zasobów
            return {"success": False, "message": self._resolve_error(resp, "Failed to fetch tasks.")}
        except Exception as e:
            return {"success": False, "message": f"Application error: {str(e)}"}

    async def _on_unexpected_disconnect(self):
        if self.session.state == SessionState.SESSION_ACTIVE:
            await self.session.handle_connection_loss()