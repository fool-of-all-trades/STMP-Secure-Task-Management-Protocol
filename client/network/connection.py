import asyncio
import logging
import ssl

from .protocol import MsgType, parse_frame
from shared.error_codes import ERROR_CODES

logger = logging.getLogger("connection")

KEEP_ALIVE_IDLE_SECONDS = 5.0
MAX_PING_FAILURES       = 2

REQUEST_TIMEOUT_SECONDS = 5.0
MAX_RETRY_ATTEMPTS      = 3


class ConnectionManager:
    def __init__(self):
        self.reader:       asyncio.StreamReader | None = None
        self.writer:       asyncio.StreamWriter | None = None
        self.is_connected: bool = False

        self._pending_requests: dict[str, asyncio.Future] = {}
        self._listen_task:      asyncio.Task | None = None
        self._ping_task:        asyncio.Task | None = None
        self._last_activity_time: float = 0.0

        self._duplicate_ids: set[str] = set()

        self.on_unexpected_disconnect = None

    # Kontekst TLS 1.3 akceptujący certyfikaty samopodpisane
    @staticmethod
    def create_ssl_context() -> ssl.SSLContext:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
        return ctx

    # Aktywność
    def update_activity(self):
        try:
            self._last_activity_time = asyncio.get_event_loop().time()
        except RuntimeError:
            pass

    # Wysyłanie ramki z obsługą retry oraz poprawnej retransmisji duplikatów
    async def send_frame(self, frame_bytes: bytes, request_id: str, timeout: float) -> dict:
        if not self.is_connected:
            raise ConnectionError("Brak połączenia z serwerem.")

        last_exception: Exception | None = None
        attempt = 1

        while attempt <= MAX_RETRY_ATTEMPTS:
            if not self.is_connected:
                raise ConnectionError("Połączenie zerwane podczas ponowienia żądania.")

            loop = asyncio.get_event_loop()
            future = loop.create_future()
            self._pending_requests[request_id] = future

            try:
                if request_id not in self._duplicate_ids:
                    self.writer.write(frame_bytes)
                    await self.writer.drain()

                response = await asyncio.wait_for(future, timeout=timeout)

                # Obsługa 301 DUPLICATE_REQUEST
                error_code = response.get("payload", {}).get("error_code")
                if (response.get("type") == MsgType.ERROR
                        and ERROR_CODES.get(error_code) == "DUPLICATE_REQUEST"):
                    logger.warning(
                        "Attempt %d/%d: 301 DUPLICATE_REQUEST dla %s — serwer przetwarza, czekam ponownie.",
                        attempt, MAX_RETRY_ATTEMPTS, request_id,
                    )
                    self._duplicate_ids.add(request_id)
                    last_exception = RuntimeError("301 DUPLICATE_REQUEST")

                    # Serwer ma jeszcze jedną szansę na dokończenie operacji
                    attempt += 1
                    continue

                # Jeśli doszło do udanej transakcji = czyszczenie flagi duplikatu
                self._duplicate_ids.discard(request_id)
                return response

            except asyncio.TimeoutError:
                logger.warning(
                    "Attempt %d/%d: timeout żądania %s (%.1f s).",
                    attempt, MAX_RETRY_ATTEMPTS, request_id, timeout,
                )
                last_exception = asyncio.TimeoutError(
                    f"Żądanie {request_id} przekroczyło limit czasu."
                )
                self._duplicate_ids.discard(request_id)

                attempt += 1
                if attempt <= MAX_RETRY_ATTEMPTS:
                    await asyncio.sleep(0.5 * attempt)  # Krótki liniowy backoff przed retransmisją
            finally:
                self._pending_requests.pop(request_id, None)

        self._duplicate_ids.discard(request_id)
        raise last_exception or asyncio.TimeoutError(
            f"Żądanie {request_id} wyczerpało {MAX_RETRY_ATTEMPTS} próby."
        )

    # Uruchomienie pętli odbioru ramek
    async def start_listen_loop(self):
        self._listen_task = asyncio.create_task(self._listen_loop())

    # Pętla odbioru ramek z uwzględnieniem Timeoutu Składania Wiadomości
    async def _listen_loop(self):
        MESSAGE_ASSEMBLY_TIMEOUT = 5.0  # Max czas na dosłanie reszty wiadomości po nagłówku
        try:
            while self.is_connected:
                # Oczekiwanie na nagłówek długości (4 bajty)
                size_header = await self.reader.readexactly(4)
                msg_size = int.from_bytes(size_header, byteorder="big")

                # Timeout składania wiadomości
                try:
                    json_bytes = await asyncio.wait_for(
                        self.reader.readexactly(msg_size),
                        timeout=MESSAGE_ASSEMBLY_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        "Timeout składania wiadomości: niepełna rama danych od serwera. Zrywam połączenie.")
                    break

                response = parse_frame(json_bytes)

                if response.get("type") != MsgType.PONG:
                    self.update_activity()
                else:
                    continue

                req_id = response.get("request_id")
                if req_id and req_id in self._pending_requests:
                    future = self._pending_requests[req_id]
                    if not future.done():
                        future.set_result(response)

        except asyncio.IncompleteReadError:
            logger.info("Serwer zamknął strumień połączenia.")
        except Exception as e:
            logger.error("Błąd pętli odbioru: %s", e)
        finally:
            if self.is_connected:
                await self.close_sockets()
                if self.on_unexpected_disconnect:
                    asyncio.create_task(self.on_unexpected_disconnect())

    # PING po KEEP_ALIVE_IDLE_SECONDS bezczynności;
    async def start_keep_alive_loop(self, ping_callback):
        self._ping_task = asyncio.create_task(self._keep_alive_loop(ping_callback))

    async def _keep_alive_loop(self, ping_callback):
        loop              = asyncio.get_event_loop()
        consecutive_fails = 0

        try:
            while self.is_connected:
                await asyncio.sleep(1.0)

                idle = loop.time() - self._last_activity_time
                if idle < KEEP_ALIVE_IDLE_SECONDS:
                    consecutive_fails = 0  # aktywność = reset licznika
                    continue

                try:
                    await ping_callback()
                    consecutive_fails = 0
                    logger.debug("Keep-alive: PING OK.")
                except Exception as e:
                    consecutive_fails += 1
                    logger.warning(
                        "Keep-alive: PING nieudany (%d/%d): %s",
                        consecutive_fails, MAX_PING_FAILURES, e,
                    )
                    if consecutive_fails >= MAX_PING_FAILURES:
                        logger.error(
                            "Keep-alive: %d kolejne PING bez odpowiedzi — zrywam połączenie.",
                            MAX_PING_FAILURES,
                        )
                        break

        except asyncio.CancelledError:
            return

        # Wypadnięcie z pętli = utrata połączenia
        if self.is_connected and self.on_unexpected_disconnect:
            await self.close_sockets()
            asyncio.create_task(self.on_unexpected_disconnect())

    # Zamykanie gniazda bez czyszczenia tokenów sesji
    async def close_sockets(self):
        self.is_connected = False

        if self._ping_task:
            self._ping_task.cancel()

        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass

        self.writer = None
        self.reader = None