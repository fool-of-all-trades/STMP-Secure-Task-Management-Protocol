import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("session_manager")


class SessionState:
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    WAITING_FOR_AUTH = "WAITING_FOR_AUTH"
    SESSION_ACTIVE = "SESSION_ACTIVE"
    SESSION_EXPIRED = "SESSION_EXPIRED"


class STMPSessionManager:
    def __init__(self, client):
        self.client = client
        self.state = SessionState.DISCONNECTED

        self.session_token = None
        self.user_id = None
        self.expires_at = None

        self.max_retry_attempts = 3
        self.is_reconnecting = False

    # Zmiana stanu sesji
    def update_state(self, new_state):
        logger.info("Session state transition: %s -> %s", self.state, new_state)
        self.state = new_state

    # Przechowywanie sesji
    def store_session(self, login_ok_payload):
        self.session_token = login_ok_payload.get("session_token")
        self.user_id = login_ok_payload.get("user_id")

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
        self.user_id = None
        self.expires_at = None
        if self.state != SessionState.DISCONNECTED:
            self.update_state(SessionState.DISCONNECTED)

    # Dla awarii sieci lub braku odp. na PING
    async def handle_connection_loss(self) -> bool:
        if self.is_reconnecting:
            return False

        self.is_reconnecting = True
        self.update_state(SessionState.DISCONNECTED)
        logger.warning("Connection lost. Initiating STMP/1.0 resume sequence...")

        # Jeśli token lokalnie wygasł, nie ma sensu próbować wznawiać sesji
        if not self.is_token_locally_valid():
            logger.error("Stored session token already expired. Re-authentication required.")
            self.clear_session()
            self.update_state(SessionState.SESSION_EXPIRED)
            self.is_reconnecting = False
            return False

        attempt = 0
        while attempt < self.max_retry_attempts and not self.client.is_connected:
            attempt += 1
            logger.info("Reconnection try %d/%d...", attempt, self.max_retry_attempts)

            try:
                # Zestawienie gniazda TCP + TLS 1.3
                ctx = self.client._get_ssl_context()
                self.client.reader, self.client.writer = await asyncio.open_connection(
                    self.client.host, self.client.port, ssl=ctx
                )
                self.client.is_connected = True
                self.client._update_activity()
                self.client._listen_task = asyncio.create_task(self.client._listen_loop())

                #  HELLO po reconnect
                hello_resp = await self.client.request("HELLO", {"message": "Reconnecting Client"})
                if hello_resp.get("type") != "HELLO_OK":
                    raise ConnectionError("Server rejected HELLO handshake during resume loop.")

                # Wysłanie RESUME_SESSION z zapisanym wcześniej tokenem
                logger.info("Sending RESUME_SESSION for token hash validation...")
                resume_resp = await self.client.request(
                    "RESUME_SESSION",
                    {"session_token": self.session_token}
                )

                if resume_resp.get("type") == "RESUME_SESSION_OK":
                    logger.info("[SUCCESS] Session successfully resumed via STMP/1.0 grace period!")
                    self.update_state(SessionState.SESSION_ACTIVE)
                    self.client._ping_task = asyncio.create_task(self.client._keep_alive_loop())
                    self.is_reconnecting = False
                    return True

                elif resume_resp.get("type") == "ERROR" and resume_resp.get("payload", {}).get("error_code") == 202:
                    logger.error("Server reported 202 SESSION_EXPIRED. Session grace period over.")
                    self.clear_session()
                    self.update_state(SessionState.SESSION_EXPIRED)
                    break

            except Exception as e:
                logger.error("Reconnection attempt %d failed: %s", attempt, e)
                # Zamknięcie niesprawnego gniazda przed kolejnym obrotem pętli
                await self.client._close_sockets()
                if attempt < self.max_retry_attempts:
                    await asyncio.sleep(2.0)

        # Jeśli pętla wygasła, a stan nie jest aktywny, sesja umiera
        self.is_reconnecting = False
        if self.state != SessionState.SESSION_ACTIVE:
            self.clear_session()
            self.update_state(SessionState.SESSION_EXPIRED)
        return False