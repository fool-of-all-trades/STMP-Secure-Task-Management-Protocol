import asyncio
import logging
import ssl
from pathlib import Path

# konfiguracja ================================================================

HOST = "0.0.0.0"
PORT = 8888

# Limity połączeń
MAX_CONNECTIONS = 100          # ile naraz może być podłączonych klientów
MAX_CONNECTIONS_PER_IP = 5     # ile połączeń z jednego IP

# Timeouty (sekundy)
READ_TIMEOUT = 60              # ile czekamy na dane od klienta
PING_INTERVAL = 30             # co ile sekund klient powinien wysłać PING

# Certyfikaty TLS – domyślnie szukamy obok tego pliku
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

# ==============================================================================

# Zbiór aktywnych połączeń – każdy wpis to (reader, writer)
_active_connections: set[asyncio.StreamWriter] = set()

# Liczba połączeń na IP
_connections_per_ip: dict[str, int] = {}


def _get_client_ip(writer: asyncio.StreamWriter) -> str:
    """Zwraca adres IP klienta lub '?' jeśli nie można ustalić."""
    peer = writer.get_extra_info("peername")
    return peer[0] if peer else "?"


def _register_connection(writer: asyncio.StreamWriter) -> bool:
    """
    Rejestruje nowe połączenie.
    Zwraca False jeśli przekroczono któryś limit.
    """
    if len(_active_connections) >= MAX_CONNECTIONS:
        logger.warning("Odrzucono połączenie – osiągnięto limit %d", MAX_CONNECTIONS)
        return False

    ip = _get_client_ip(writer)
    count = _connections_per_ip.get(ip, 0)
    if count >= MAX_CONNECTIONS_PER_IP:
        logger.warning("Odrzucono połączenie z %s – limit per-IP (%d)", ip, MAX_CONNECTIONS_PER_IP)
        return False

    _active_connections.add(writer)
    _connections_per_ip[ip] = count + 1
    logger.info("Nowe połączenie: %s  (aktywnych: %d)", ip, len(_active_connections))
    return True


def _unregister_connection(writer: asyncio.StreamWriter) -> None:
    """Usuwa połączenie."""
    _active_connections.discard(writer)
    ip = _get_client_ip(writer)
    count = _connections_per_ip.get(ip, 1)
    if count <= 1:
        _connections_per_ip.pop(ip, None)
    else:
        _connections_per_ip[ip] = count - 1
    logger.info("Rozłączono: %s  (aktywnych: %d)", ip, len(_active_connections))


# obsługa klienta =================================================================

async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:

    if not _register_connection(writer):
        # Przekroczono limit 
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        return

    ip = _get_client_ip(writer)

    try:
        # TODO parser -> router -> handler
        await _client_loop(reader, writer, ip)
    except Exception as exc:
        logger.exception("Nieobsłużony wyjątek dla klienta %s: %s", ip, exc)
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
    """Główna pętla komunikacji z klientem."""

    logger.debug("Rozpoczęto pętlę dla %s", ip)

    while True:
        try:
            # Oczekujemy na dane od klienta z określonym timeoutem
            data = await asyncio.wait_for(reader.read(65536), timeout=READ_TIMEOUT)
        except asyncio.TimeoutError:
            logger.info("Timeout klienta %s – zamykam połączenie", ip)
            break
        except asyncio.IncompleteReadError:
            logger.info("Klient %s rozłączył się", ip)
            break

        if not data:
            logger.info("Klient %s zamknął połączenie", ip)
            break

        # TODO przekazać `data` do parsera i routera
        # response = await dispatch(data, writer, ip)
        # writer.write(response)
        # await writer.drain()

        logger.debug("Odebrano %d bajtów od %s", len(data), ip)


# TLS ===========================================================================

def _build_ssl_context() -> ssl.SSLContext:
    """Tworzy kontekst TLS 1.3 z certyfikatem serwera."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3

    if not CERT_FILE.exists() or not KEY_FILE.exists():
        raise FileNotFoundError(
            f"Nie znaleziono certyfikatów TLS.\n"
            f"  cert: {CERT_FILE}\n"
            f"  key:  {KEY_FILE}\n"
            f"Wygeneruj self-signed cert:\n"
            f"  mkdir -p server/certs\n"
            f"  openssl req -x509 -newkey rsa:4096 -keyout server/certs/server.key "
            f"-out server/certs/server.crt -days 365 -nodes -subj '/CN=localhost'"
        )

    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    logger.info("TLS: załadowano certyfikat %s", CERT_FILE)
    return ctx


# serwer ==========================================================================

async def main() -> None:
    ssl_ctx = _build_ssl_context()

    server = await asyncio.start_server(
        handle_client,
        host=HOST,
        port=PORT,
        ssl=ssl_ctx,
        limit=65536,          # bufor per połączenie (limit 64KB)
        backlog=128,          # kolejka oczekujących połączeń
    )

    addrs = [str(s.getsockname()) for s in server.sockets]
    logger.info("Serwer nasłuchuje na %s (TLS 1.3, max %d połączeń)", addrs, MAX_CONNECTIONS)

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Serwer zatrzymany.")