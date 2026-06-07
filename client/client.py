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

    def _get_local_ip(self) -> str | None:
        try:
            if self.connection.writer:
                sock = self.connection.writer.get_extra_info("socket")
                if sock:
                    return sock.getsockname()[0]
        except Exception:
            pass
        return None

    async def connect(self) -> bool:
        if self.is_connected:
            return True

        try:
            ctx = ConnectionManager.create_ssl_context()
            self.connection.reader, self.connection.writer = (
                await asyncio.open_connection(self.host, self.port, ssl=ctx)
            )
            self.is_connected = True
            self.connection.update_activity()

            await self.connection.start_listen_loop()

            resp = await self.request("HELLO", {"message": "Client HELLO"})
            if resp.get("type") == "HELLO_OK":
                self.session.update_state(SessionState.CONNECTED)

                await self.connection.start_keep_alive_loop(
                    lambda: self.request("PING", {})
                )
                return True

            await self.connection.close_sockets()
            return False

        except Exception as e:
            logger.error("Błąd połączenia z %s:%d: %s", self.host, self.port, e)
            self.is_connected = False
            return False

    # Główne żądanie sieciowe
    async def request(self, msg_type: str, payload: dict, timeout: float = 5.0) -> dict:
        # Weryfikacja IP przed wysłaniem (token powiązany jest z IP z chwili logowania)
        if (msg_type not in MsgType.NO_AUTH_REQUIRED
                and self.session.state == SessionState.SESSION_ACTIVE
                and not self.session.is_ip_valid(self._get_local_ip())):
            logger.error("IP klienta zmieniło się od czasu logowania — odrzucam żądanie %s.", msg_type)
            self.session.clear_session()
            self.session.update_state(SessionState.SESSION_EXPIRED)
            return {"type": MsgType.ERROR, "payload": {"error_code": None, "message": "Client IP mismatch — session invalidated."}}

        frame = build_frame(msg_type, payload, self.session.session_token)
        request_id = extract_request_id(frame)

        response = await self.connection.send_frame(frame, request_id, timeout)
        logger.debug(response.get("type", "?"))

        # Aktualizacja stanu sesji oraz tokenu przy pierwszym zalogowaniu
        if response.get("type") == MsgType.LOGIN_OK:
            client_ip = self._get_local_ip()
            self.session.store_session(response["payload"], client_ip=client_ip)
            logger.info("Sesja powiązana z IP: %s (STMP/1.0 §27)", client_ip)

        elif response.get("type") == MsgType.BYE:
            self.session.clear_session()

        elif (response.get("type") == MsgType.ERROR
              and ERROR_CODES.get(response.get("payload", {}).get("error_code")) == "ACCESS_DENIED"):
            logger.error("403 ACCESS_DENIED — token sesji nie pasuje do bieżącego IP.")
            self.session.clear_session()
            self.session.update_state(SessionState.SESSION_EXPIRED)

        # Odświeżenie licznika bezczynności — dopiero po odebraniu odpowiedzi.
        elif msg_type not in (MsgType.PING, MsgType.HELLO, MsgType.BYE):
            self.session.notify_activity()

        return response

    # Pobranie tekstu na podstawie kodu błędu
    def _resolve_error(self, resp: dict, fallback: str) -> str:
        payload = resp.get("payload", {})
        error_code = payload.get("error_code")
        if error_code in ERROR_CODES:
            return f"{ERROR_CODES[error_code]} ({payload.get('message', fallback)})"
        return payload.get("message", fallback)

    async def disconnect(self) -> dict:
        try:
            resp = await self.request("BYE", {})
            await self.connection.close_sockets()
            self.session.clear_session()
            return {"success": True, "message": "Disconnected successfully."}
        except Exception as e:
            return {"success": False, "message": f"Network error: {str(e)}"}

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
        logger.warning("Wykryto nieoczekiwane rozłączenie — przekazuję do SessionManagera.")
        if self.session.state == SessionState.SESSION_ACTIVE:
            await self.session.handle_connection_loss()