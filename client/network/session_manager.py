import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("session_manager")


# Stany sesji
class SessionState:
    DISCONNECTED      = "DISCONNECTED"
    CONNECTED         = "CONNECTED"
    WAITING_FOR_AUTH  = "WAITING_FOR_AUTH"
    SESSION_ACTIVE    = "SESSION_ACTIVE"
    SESSION_EXPIRED   = "SESSION_EXPIRED"


# Menedżer sesji
class STMPSessionManager:
    def __init__(self, client):
        self.client = client
        self.state  = SessionState.DISCONNECTED

        self.session_token: str | None      = None
        self.user_id:       str | None      = None
        self.expires_at:    datetime | None = None

        self.max_retry_attempts = 3
        self.is_reconnecting    = False

    # Zmiana stanu sesji
    def update_state(self, new_state: str):
        logger.info("Sesja: %s → %s", self.state, new_state)
        self.state = new_state

    # Przechowywanie i walidacja tokenu
    def store_session(self, login_ok_payload: dict):
        self.session_token = login_ok_payload.get("session_token")
        self.user_id       = login_ok_payload.get("user_id")

        # Parsowanie czasu wygaśnięcia z formatu ISO serwera
        exp_str = login_ok_payload.get("expires_at", "").replace("Z", "+00:00")
        try:
            self.expires_at = datetime.fromisoformat(exp_str)
        except ValueError:
            self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        self.update_state(SessionState.SESSION_ACTIVE)

    # Sprawdzanie czy sesja nie wygasła dla czasu lokalnego
    def is_token_locally_valid(self) -> bool:
        if not self.session_token or not self.expires_at:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    # Czysta sesja
    def clear_session(self):
        self.session_token = None
        self.user_id       = None
        self.expires_at    = None
        if self.state != SessionState.DISCONNECTED:
            self.update_state(SessionState.DISCONNECTED)

    # Obsługa utraty połączenia i reconnect
    async def handle_connection_loss(self) -> bool:
        if self.is_reconnecting:
            return False

        self.is_reconnecting = True
        self.update_state(SessionState.DISCONNECTED)
        logger.warning("Utrata połączenia. Inicjowanie sekwencji wznawiania STMP/1.0...")

        # Jeśli token lokalnie wygasł, nie ma sensu próbować wznawiać sesji
        if not self.is_token_locally_valid():
            logger.error("Token sesji wygasł lokalnie — wymagane ponowne logowanie.")
            self.clear_session()
            self.update_state(SessionState.SESSION_EXPIRED)
            self.is_reconnecting = False
            return False

        success = await self._retry_reconnect()
        self.is_reconnecting = False

        if not success and self.state != SessionState.SESSION_ACTIVE:
            self.clear_session()
            self.update_state(SessionState.SESSION_EXPIRED)

        return success

    # Próba ponownego połączenia i wysłania RESUME_SESSION
    async def _retry_reconnect(self) -> bool:
        for attempt in range(1, self.max_retry_attempts + 1):
            logger.info("Próba reconnect %d/%d...", attempt, self.max_retry_attempts)

            try:
                connected = await self._establish_raw_connection()
                if not connected:
                    raise ConnectionError("Nie udało się zestawić połączenia TCP/TLS.")

                resume_ok = await self._send_resume_session()
                if resume_ok:
                    return True
                else:
                    # Serwer zwrócił 202 SESSION_EXPIRED = nie ma sensu próbować dalej
                    break

            except Exception as e:
                logger.error("Próba %d nie powiodła się: %s", attempt, e)
                await self.client.connection.close_sockets()
                if attempt < self.max_retry_attempts:
                    await asyncio.sleep(2.0)

        return False

    # Zestawienie gniazda TCP/TLS i uruchomienie pętli odbioru
    async def _establish_raw_connection(self) -> bool:
        from .connection import ConnectionManager

        ctx = ConnectionManager.create_ssl_context()
        self.client.connection.reader, self.client.connection.writer = (
            await asyncio.open_connection(self.client.host, self.client.port, ssl=ctx)
        )
        self.client.connection.is_connected = True
        self.client.connection.update_activity()
        await self.client.connection.start_listen_loop()

        hello_resp = await self.client.request("HELLO", {"message": "Reconnecting Client"})
        if hello_resp.get("type") != "HELLO_OK":
            raise ConnectionError("Serwer odrzucił handshake HELLO podczas reconnect.")

        return True

    # Wysłanie RESUME_SESSION
    async def _send_resume_session(self) -> bool:
        logger.info("Wysyłanie RESUME_SESSION (walidacja tokenu)...")
        resp = await self.client.request(
            "RESUME_SESSION",
            {"session_token": self.session_token},
        )

        if resp.get("type") == "RESUME_SESSION_OK":
            logger.info("[OK] Sesja wznowiona pomyślnie przez STMP/1.0 grace period.")
            self.update_state(SessionState.SESSION_ACTIVE)
            await self.client.connection.start_keep_alive_loop(
                lambda: self.client.request("PING", {})
            )
            return True

        error_code = resp.get("payload", {}).get("error_code")
        if resp.get("type") == "ERROR" and error_code == 202:
            logger.error("Serwer zwrócił 202 SESSION_EXPIRED — grace period minął.")
            self.clear_session()
            self.update_state(SessionState.SESSION_EXPIRED)
            return False

        raise ConnectionError(f"Nieoczekiwana odpowiedź na RESUME_SESSION: {resp.get('type')}")