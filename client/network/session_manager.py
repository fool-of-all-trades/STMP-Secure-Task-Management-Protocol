import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta

from shared.error_codes import ERROR_CODES

logger = logging.getLogger("session_manager")

SESSION_IDLE_TIMEOUT = 60.0

# Stany sesji
class SessionState:
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    WAITING_FOR_AUTH = "WAITING_FOR_AUTH"
    SESSION_ACTIVE = "SESSION_ACTIVE"
    SESSION_EXPIRED = "SESSION_EXPIRED"


# Menedżer sesji
class STMPSessionManager:
    def __init__(self, client):
        self.client = client
        self.state = SessionState.DISCONNECTED

        self.session_token: str | None = None
        self.user_id: str | None = None
        self.expires_at: datetime | None = None

        # IP klienta zapamiętane przy logowaniu (powiązanie tokenu z IP)
        self.bound_ip: str | None = None

        self.max_retry_attempts = 3
        self.is_reconnecting = False

        # Zmienna przechowująca dokładny czas systemowy ostatniej aktywności użytkownika
        self._last_activity_time: float = 0.0
        self._idle_task: asyncio.Task | None = None

    def update_state(self, new_state: str):
        logger.info("Sesja: %s → %s", self.state, new_state)
        self.state = new_state

    # Wywoływane WYŁĄCZNIE przy pełnym zalogowaniu (LOGIN_OK) - ustawia czas życia tokenu
    def store_session(self, login_ok_payload: dict, client_ip: str | None = None):
        self.session_token = login_ok_payload.get("session_token")
        self.user_id = login_ok_payload.get("user_id")
        self.bound_ip = client_ip

        # Parsowanie czasu wygaśnięcia z formatu ISO serwera
        exp_str = login_ok_payload.get("expires_at", "").replace("Z", "+00:00")
        try:
            self.expires_at = datetime.fromisoformat(exp_str)
        except ValueError:
            # Jeśli serwer nie podał poprawnego czasu, lokalnie dajemy mu 30 minut ważności
            self.expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        self.update_state(SessionState.SESSION_ACTIVE)

        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

        self.update_activity_timestamp()
        self._start_idle_timer()

    def update_activity_timestamp(self):
        # Pobieranie czas procesora
        self._last_activity_time = time.monotonic()

    # Odświeżenie timera bezczynności
    def notify_activity(self):
        if self.state == SessionState.SESSION_ACTIVE:
            self.update_activity_timestamp()

    def _start_idle_timer(self):
        # Jeśli pętla monitorująca już działa, nie duplikujemy zadania
        if self._idle_task and not self._idle_task.done():
            return
        try:
            self._idle_task = asyncio.get_event_loop().create_task(
                self._idle_timeout_loop()
            )
        except RuntimeError:
            pass

    # Pętla sprawdzająca w czasie rzeczywistym czas od ostatniej akcji użytkownika
    async def _idle_timeout_loop(self):
        try:
            while True:
                await asyncio.sleep(1.0)

                if self.state != SessionState.SESSION_ACTIVE:
                    break

                # Faktyczny czas bezczynności
                idle_duration = time.monotonic() - self._last_activity_time

                if idle_duration >= SESSION_IDLE_TIMEOUT:
                    logger.warning(
                        "Sesja bezczynna przez %.1f s — wymuszam SESSION_EXPIRED i reautentykację.",
                        idle_duration,
                    )
                    # SESSION_EXPIRED przed clear_session, żeby nie nadpisał go przez DISCONNECTED
                    self.state = SessionState.SESSION_EXPIRED
                    self.clear_session()
                    self.update_state(SessionState.SESSION_EXPIRED)

                    # Wywołanie okna reautentykacji w GUI
                    if self.client.connection.on_unexpected_disconnect:
                        asyncio.create_task(self.client.connection.on_unexpected_disconnect())
                    break
        except asyncio.CancelledError:
            return

    def is_token_locally_valid(self) -> bool:
        if not self.session_token or not self.expires_at:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    def is_ip_valid(self, current_ip: str | None) -> bool:
        if self.bound_ip is None or current_ip is None:
            return True
        return self.bound_ip == current_ip

    def clear_session(self):
        self.session_token = None
        self.user_id = None
        self.expires_at = None
        self.bound_ip = None

        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None

        if self.state not in (SessionState.DISCONNECTED, SessionState.SESSION_EXPIRED):
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

    # Wysłanie RESUME_SESSION (wznowienie połączenia w ramach tej samej sesji)
    async def _send_resume_session(self) -> bool:
        logger.info("Wysyłanie RESUME_SESSION (walidacja tokenu)...")
        resp = await self.client.request(
            "RESUME_SESSION",
            {"session_token": self.session_token},
        )

        if resp.get("type") == "RESUME_SESSION_OK":
            logger.info("[OK] Sesja wznowiona pomyślnie przez STMP/1.0 grace period.")
            self.update_state(SessionState.SESSION_ACTIVE)

            if self._idle_task and not self._idle_task.done():
                self._idle_task.cancel()
            self._idle_task = None
            self.update_activity_timestamp()
            self._start_idle_timer()

            await self.client.connection.start_keep_alive_loop(
                lambda: self.client.request("PING", {})
            )
            return True

        error_code = resp.get("payload", {}).get("error_code")
        if resp.get("type") == "ERROR":
            # Każdy ERROR na RESUME_SESSION (w tym nieznany kod) = sesja nie do wznowienia.
            if ERROR_CODES.get(error_code) == "SESSION_EXPIRED":
                logger.error("Serwer zwrócił SESSION_EXPIRED (202) — grace period minął.")
            else:
                logger.error(
                    "Serwer odrzucił RESUME_SESSION z błędem %s — wymagane ponowne logowanie.",
                    error_code or resp.get("payload", {}).get("message", "?"),
                )
            self.clear_session()
            self.update_state(SessionState.SESSION_EXPIRED)
            return False

        raise ConnectionError(f"Nieoczekiwana odpowiedź na RESUME_SESSION: {resp.get('type')}")