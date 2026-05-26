import asyncio
import logging
import ssl
from pathlib import Path

from server.protocol.parser import parse_message, build_response
from server.protocol.router import dispatch, ConnectionState

# konfiguracja ================================================================

HOST = "0.0.0.0"
PORT = 8888

MAX_CONNECTIONS = 100
MAX_CONNECTIONS_PER_IP = 5

READ_TIMEOUT = 60
PING_INTERVAL = 30

_BASE = Path(__file__).parent
CERT_FILE = _BASE / "certs" / "server.crt"
KEY_FILE  = _BASE / "certs" / "server.key"

# logi ======================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("server")

# stan globalny ===============================================================

_active_connections: set[asyncio.StreamWriter] = set()
_connections_per_ip: dict[str, int] = {}


def _get_client_ip(writer: asyncio.StreamWriter) -> str:
    peer = writer.get_extra_info("peername")
    return peer[0] if peer else "?"


def _register_connection(writer: asyncio.StreamWriter) -> bool:
    if len(_active_connections) >= MAX_CONNECTIONS:
        logger.warning("Odrzucono polaczenie – osiagnieto limit %d", MAX_CONNECTIONS)
        return False

    ip = _get_client_ip(writer)
    count = _connections_per_ip.get(ip, 0)
    if count >= MAX_CONNECTIONS_PER_IP:
        logger.warning("Odrzucono polaczenie z %s – limit per-IP (%d)", ip, MAX_CONNECTIONS_PER_IP)
        return False

    _active_connections.add(writer)
    _connections_per_ip[ip] = count + 1
    logger.info("Nowe polaczenie: %s  (aktywnych: %d)", ip, len(_active_connections))
    return True


def _unregister_connection(writer: asyncio.StreamWriter) -> None:
    _active_connections.discard(writer)
    ip = _get_client_ip(writer)
    count = _connections_per_ip.get(ip, 1)
    if count <= 1:
        _connections_per_ip.pop(ip, None)
    else:
        _connections_per_ip[ip] = count - 1
    logger.info("Rozlaczono: %s  (aktywnych: %d)", ip, len(_active_connections))


# obsługa klienta =============================================================

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    if not _register_connection(writer):
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return

    ip = _get_client_ip(writer)

    try:
        await _client_loop(reader, writer, ip)
    except Exception as exc:
        logger.exception("Nieobsluzony wyjatek dla klienta %s: %s", ip, exc)
    finally:
        _unregister_connection(writer)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def _client_loop(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    ip: str,
) -> None:
    """Glowna petla komunikacji z klientem."""

    # Stan polaczenia i token sesji per-polaczenie
    state = ConnectionState.CONNECTED
    session_token: str | None = None

    while True:
        try:
            parse_result = await asyncio.wait_for(
                parse_message(reader),
                timeout=READ_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.info("Timeout klienta %s – zamykam polaczenie", ip)
            break
        except asyncio.IncompleteReadError:
            logger.info("Klient %s rozlaczyl sie", ip)
            break
        except OSError as exc:
            logger.debug("Polaczenie zerwane dla %s: %s", ip, exc)
            break
        except Exception as exc:
            logger.warning("Blad parsowania dla %s: %s", ip, exc)
            break

        # Blad parsowania – wyslij ERROR i czekaj na kolejna wiadomosc
        if not parse_result["ok"]:
            error_code = parse_result["error_code"]
            error_msg = parse_result["message"]
            logger.warning("Parse error %d dla %s: %s", error_code, ip, error_msg)
            try:
                writer.write(build_response("ERROR", {"error_code": error_code, "message": error_msg}))
                await writer.drain()
            except Exception:
                break
            continue

        message = parse_result["message"]
        msg_type = message["type"]
        request_id = message["request_id"]

        logger.info("Odebrano %s od %s (request_id: %s)", msg_type, ip, request_id)

        # Router
        response_type, payload, new_state = dispatch(message, state, ip, session_token)

        # Aktualizuj stan i token po udanym LOGIN
        if new_state is not None:
            state = new_state

        if response_type == "LOGIN_OK":
            session_token = payload.get("session_token")

        if response_type == "RESUME_SESSION_OK":
            session_token = message["payload"].get("session_token")

        # Wyslij odpowiedz
        try:
            writer.write(build_response(response_type, payload, request_id))
            await writer.drain()
        except Exception as exc:
            logger.warning("Nie udalo sie wyslac odpowiedzi do %s: %s", ip, exc)
            break

        # Jesli BYE – zamknij polaczenie
        if response_type == "BYE" or state == ConnectionState.DISCONNECTED:
            logger.info("Klient %s wylogowal sie", ip)
            break


# TLS =========================================================================

def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3

    if not CERT_FILE.exists() or not KEY_FILE.exists():
        raise FileNotFoundError(
            f"Nie znaleziono certyfikatow TLS.\n"
            f"  cert: {CERT_FILE}\n"
            f"  key:  {KEY_FILE}\n"
        )

    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    logger.info("TLS: zaladowano certyfikat %s", CERT_FILE)
    return ctx


# serwer ======================================================================

async def main() -> None:
    def exception_handler(loop, context):
        exc = context.get("exception")
        if isinstance(exc, ConnectionResetError):
            return
        loop.default_exception_handler(context)

    loop = asyncio.get_event_loop()
    loop.set_exception_handler(exception_handler)

    ssl_ctx = _build_ssl_context()

    server = await asyncio.start_server(
        handle_client,
        host=HOST,
        port=PORT,
        ssl=ssl_ctx,
        limit=65536,
        backlog=128,
    )

    addrs = [str(s.getsockname()) for s in server.sockets]
    logger.info("Serwer nasluchuje na %s (TLS 1.3, max %d polaczen)", addrs, MAX_CONNECTIONS)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Serwer zatrzymany.")