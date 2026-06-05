import asyncio
import logging
import ssl
import uuid
from datetime import datetime, timezone
import json

from .session_manager import STMPSessionManager, SessionState

logger = logging.getLogger("client")

class STMPClient:
    def __init__(self, host="127.0.0.1", port=8888):
        self.host = host
        self.port = port
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.is_connected = False
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._listen_task: asyncio.Task | None = None
        self._ping_task: asyncio.Task | None = None
        self._last_activity_time = 0.0

        self.session = STMPSessionManager(self)

    @property
    def session_token(self):
        return self.session.session_token

    def _get_ssl_context(self) -> ssl.SSLContext:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_3
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # Akceptacja samopodpisanego certyfikatu testowego
        return ctx

    async def connect(self) -> bool:
        if self.is_connected:
            return True

        ctx = self._get_ssl_context()
        try:
            logger.info("Connecting to %s:%d via TLS 1.3...", self.host, self.port)
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port, ssl=ctx)
            self.is_connected = True
            self._update_activity()

            # Uruchomienie pętli odbierającej komunikaty w tle
            self._listen_task = asyncio.create_task(self._listen_loop())

            # Handshake aplikacyjny
            response = await self.request("HELLO", {"message": "Hello from GUI Client"})
            if response.get("type") == "HELLO_OK":
                logger.info("Handshake successful: HELLO_OK received.")
                self.session.update_state(SessionState.CONNECTED)

                # Uruchomienie mechanizmu podtrzymywania połączenia (Keep-Alive)
                self._ping_task = asyncio.create_task(self._keep_alive_loop())
                return True
            else:
                logger.error("Server rejected handshake: %s", response)
                await self.disconnect()
                return False
        except Exception as e:
            logger.error("Failed to connect to server: %s", e)
            self.is_connected = False
            return False

    # Śledzenie aktywności w panelu użytkownika
    def _update_activity(self):
        try:
            loop = asyncio.get_event_loop()
            self._last_activity_time = loop.time()
        except RuntimeError:
            pass

    # Automatyczne wstrzykiwanie tokenu do żądań użytkownika
    def _build_frame(self, msg_type: str, payload: dict) -> bytes:
        if self.session.session_token and msg_type not in {"PING", "HELLO", "BYE"}:
            if "session_token" not in payload:
                payload["session_token"] = self.session.session_token

        message = {
            "type": msg_type,
            "version": "1.0",
            "request_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "payload": payload
        }
        json_bytes = json.dumps(message, ensure_ascii=False).encode("utf-8")
        size_bytes = len(json_bytes).to_bytes(4, byteorder="big")
        return size_bytes + json_bytes

    # Żądanie od serwera ramki
    async def request(self, msg_type: str, payload: dict, timeout: float = 5.0) -> dict:
        if not self.is_connected:
            raise ConnectionError("Client is not connected to the server.")

        frame_bytes = self._build_frame(msg_type, payload)
        msg_dict = json.loads(frame_bytes[4:].decode("utf-8"))
        req_id = msg_dict["request_id"]

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending_requests[req_id] = future

        try:
            self.writer.write(frame_bytes)
            await self.writer.drain()
            self._update_activity()

            response = await asyncio.wait_for(future, timeout=timeout)

            # Rejestracja stanu sesji w menedżerze na podstawie odpowiedzi sieciowych
            if response.get("type") == "LOGIN_OK":
                self.session.store_session(response["payload"])
            elif response.get("type") == "BYE":
                self.session.clear_session()

            return response
        except asyncio.TimeoutError:
            logger.warning("Request %s triggered an operational timeout.", req_id)
            raise asyncio.TimeoutError(f"Request {msg_type} timed out.")
        finally:
            self._pending_requests.pop(req_id, None)

    # Tworzenie nowych zadań
    async def create_task(self, title: str, description: str, status: str) -> dict:
        payload = {
            "title": title,
            "description": description,
            "status": status
        }
        try:
            response = await self.request("CREATE_TASK", payload)
            if response.get("type") == "TASK_CREATED":
                return {"success": True, "message": "Task created successfully!"}

            # Pobieranie błędu z payloadu serwera
            error_msg = response.get("payload", {}).get("message", "Failed to create task.")
            return {"success": False, "message": error_msg}
        except Exception as e:
            return {"success": False, "message": f"Network error: {str(e)}"}

    # Edycja zadań
    async def update_task(self, task_id: str, title: str, description: str, status: str) -> dict:
        payload = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "status": status
        }
        try:
            response = await self.request("UPDATE_TASK", payload)
            if response.get("type") == "TASK_UPDATED":
                return {"success": True, "message": "Task updated successfully!"}

            error_msg = response.get("payload", {}).get("message", "Failed to update task.")
            return {"success": False, "message": error_msg}
        except Exception as e:
            return {"success": False, "message": f"Network error: {str(e)}"}

    # Usuniecie zadania
    async def delete_task(self, task_id: str) -> dict:
        payload = {
            "task_id": task_id
        }
        try:
            response = await self.request("DELETE_TASK", payload)
            if response.get("type") == "TASK_DELETED":
                return {"success": True, "message": "Task deleted successfully!"}

            error_msg = response.get("payload", {}).get("message", "Failed to delete task.")
            return {"success": False, "message": error_msg}
        except Exception as e:
            return {"success": False, "message": f"Network error: {str(e)}"}

    # Pętla wysyłająca komunikaty PING po 30 sekundach bezczynności
    async def _keep_alive_loop(self):
        loop = asyncio.get_event_loop()
        consecutive_failures = 0
        try:
            while self.is_connected:
                await asyncio.sleep(1.0)
                now = loop.time()

                if now - self._last_activity_time >= 30.0:
                    try:
                        await self.request("PING", {})
                        consecutive_failures = 0  # Reset po odebraniu PONG
                    except Exception:
                        consecutive_failures += 1
                        # Brak odpowiedzi na 2 kolejne PING = zerwanie połączenia
                        if consecutive_failures >= 2:
                            logger.error("Keep-alive timeout. 2 consecutive PINGs failed.")
                            break
        except asyncio.CancelledError:
            pass

        # Wypadliśmy z pętli przy aktywnej sesji = uruchomienie reconnect
        if self.is_connected or self.session.state == SessionState.SESSION_ACTIVE:
            await self._close_sockets()
            asyncio.create_task(self.session.handle_connection_loss())

    # Ciągłe odczytywanie ramek
    async def _listen_loop(self):
        try:
            while self.is_connected:
                # Odczyt 4 bajtów długości ramki
                size_header = await self.reader.readexactly(4)
                msg_size = int.from_bytes(size_header, byteorder="big")

                # Odczyt całości JSONa na podstawie odebranej długości
                json_bytes = await self.reader.readexactly(msg_size)
                response_dict = json.loads(json_bytes.decode("utf-8"))

                self._update_activity()

                # Odfiltrowanie i skonsumowanie odpowiedzi PONG w tle
                if response_dict.get("type") == "PONG":
                    continue

                req_id = response_dict.get("request_id")
                if req_id in self._pending_requests:
                    future = self._pending_requests[req_id]
                    if not future.done():
                        future.set_result(response_dict)
        except asyncio.IncompleteReadError:
            logger.info("Server closed connection stream clean.")
        except Exception as e:
            logger.error("Error in client incoming stream loop: %s", e)
        finally:
            # Obsługa niespodziewanego rozłączenia wykrytego na gnieździe
            if self.is_connected:
                await self._close_sockets()
                if self.session.state == SessionState.SESSION_ACTIVE:
                    asyncio.create_task(self.session.handle_connection_loss())

    # Bezpieczne zamknięcie gniazda sieciowego (bez resetowania tokenów)
    async def _close_sockets(self):
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

    # Całkowite wylogowanie i zamknięcie połączenia
    async def disconnect(self):
        self.session.clear_session()
        if self._ping_task:
            self._ping_task.cancel()
        if self._listen_task:
            self._listen_task.cancel()

        if self.is_connected and self.writer:
            # Wysłanie komunikatu pożegnalnego przed zamknięciem gniazda
            try:
                await asyncio.wait_for(self.request("BYE", {}), timeout=1.5)
            except Exception:
                pass
        await self._close_sockets()