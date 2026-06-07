import asyncio
import logging
import ssl

from .protocol import MsgType, parse_frame

logger = logging.getLogger("connection")

KEEP_ALIVE_IDLE_SECONDS = 30.0   # czas bezczynności przed wysłaniem PING
MAX_PING_FAILURES       = 2      # ile nieudanych PINGów kończy połączenie


class ConnectionManager:
    def __init__(self):
        self.reader:       asyncio.StreamReader | None = None
        self.writer:       asyncio.StreamWriter | None = None
        self.is_connected: bool = False

        self._pending_requests: dict[str, asyncio.Future] = {}
        self._listen_task:      asyncio.Task | None = None
        self._ping_task:        asyncio.Task | None = None
        self._last_activity_time: float = 0.0

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

    # Wysyłanie ramki i rejestracja Future
    async def send_frame(self, frame_bytes: bytes, request_id: str, timeout: float) -> dict:
        if not self.is_connected:
            raise ConnectionError("Brak połączenia z serwerem.")

        loop  = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending_requests[request_id] = future

        try:
            self.writer.write(frame_bytes)
            await self.writer.drain()
            self.update_activity()
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"Żądanie {request_id} przekroczyło limit czasu.")
        finally:
            self._pending_requests.pop(request_id, None)

    # Pętla odbioru ramek
    async def start_listen_loop(self):
        self._listen_task = asyncio.create_task(self._listen_loop())

    async def _listen_loop(self):
        try:
            while self.is_connected:
                size_header = await self.reader.readexactly(4)
                msg_size    = int.from_bytes(size_header, byteorder="big")
                json_bytes  = await self.reader.readexactly(msg_size)

                response = parse_frame(json_bytes)
                self.update_activity()

                # PONG obsługujemy tutaj — nie trafia do czekających Future
                if response.get("type") == MsgType.PONG:
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

    # Pętla keep-alive (PING co 30 s bezczynności)
    async def start_keep_alive_loop(self, ping_callback):
        self._ping_task = asyncio.create_task(
            self._keep_alive_loop(ping_callback)
        )

    async def _keep_alive_loop(self, ping_callback):
        loop               = asyncio.get_event_loop()
        consecutive_fails  = 0

        try:
            while self.is_connected:
                await asyncio.sleep(1.0)

                idle = loop.time() - self._last_activity_time
                if idle < KEEP_ALIVE_IDLE_SECONDS:
                    continue

                try:
                    await ping_callback()
                    consecutive_fails = 0
                except Exception:
                    consecutive_fails += 1
                    if consecutive_fails >= MAX_PING_FAILURES:
                        logger.error("Keep-alive: %d kolejne PING bez odpowiedzi — zrywam.", MAX_PING_FAILURES)
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