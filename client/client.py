import asyncio
import logging

from .connection     import ConnectionManager
from .protocol       import MsgType, build_frame, extract_request_id
from .session_manager import STMPSessionManager, SessionState
from .task_api       import TaskAPI

logger = logging.getLogger("client")


class STMPClient(TaskAPI):
    def __init__(self, host: str = "127.0.0.1", port: int = 8888):
        self.host = host
        self.port = port

        self.connection = ConnectionManager()
        self.session    = STMPSessionManager(self)

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
        frame      = build_frame(msg_type, payload, self.session.session_token)
        request_id = extract_request_id(frame)

        response = await self.connection.send_frame(frame, request_id, timeout)

        # Aktualizacja stanu sesji na podstawie odpowiedzi
        if response.get("type") == MsgType.LOGIN_OK:
            self.session.store_session(response["payload"])
        elif response.get("type") == MsgType.BYE:
            self.session.clear_session()

        return response

    # Callback utraty połączenia
    async def _on_unexpected_disconnect(self):
        if self.session.state == SessionState.SESSION_ACTIVE:
            await self.session.handle_connection_loss()