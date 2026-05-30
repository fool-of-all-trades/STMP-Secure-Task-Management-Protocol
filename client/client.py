import asyncio
import logging
import ssl
from pathlib import Path

# Logi ========================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("client")

# Konfiguracja ================================================================
SERVER_HOST = "127.0.0.1"  # Adres serwera (localhost do testów)
SERVER_PORT = 8888

_BASE = Path(__file__).parent
# Ścieżka do certyfikatu serwera
CERT_FILE = _BASE.parent / "server" / "certs" / "server.crt"


# TLS Context =================================================================
def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_3

    if CERT_FILE.exists():
        ctx.load_verify_locations(cafile=CERT_FILE)
        ctx.check_hostname = False
        logger.info("TLS: Loaded server certificate %s for verification.", CERT_FILE)
    else:
        logger.warning("Certificate file not found at: %s", CERT_FILE)
        logger.warning("Running in NO VERIFICATION mode for testing certificate!")
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    return ctx


# Główna funkcja klienta =======================================================
async def main() -> None:
    ssl_ctx = _build_ssl_context()

    logger.info("Attempting to connect to server %s:%d using TLS 1.3...", SERVER_HOST, SERVER_PORT)

    try:
        reader, writer = await asyncio.open_connection(
            host=SERVER_HOST,
            port=SERVER_PORT,
            ssl=ssl_ctx
        )

        # Poniższy blok wykona się TYLKO, gdy handshake TLS zakończy się sukcesem
        peername = writer.get_extra_info("peername")
        ssl_object = writer.get_extra_info("ssl_object")
        cipher = ssl_object.cipher() if ssl_object else ("Unknown", "None", 0)

        print("\n" + "=" * 60)
        print("  [SUCCESS] Connected to STMP server successfully!")
        print(f"  Server address: {peername[0]}:{peername[1]}")
        print(f"  Encryption protocol: {cipher[1]} ({cipher[0]})")
        print("=" * 60 + "\n")

        logger.info("Connection is active. Closing in 3 seconds...")
        await asyncio.sleep(3)

        logger.info("Closing the connection...")
        writer.close()
        await writer.wait_closed()
        logger.info("Connection closed successfully.")

    except ssl.SSLError as e:
        logger.error("[TLS ERROR] Encryption handshake error: %s", e)
    except ConnectionRefusedError:
        logger.error("[ERROR] The server refused the connection. Make sure the server is running on the port %d.",
                     SERVER_PORT)
    except Exception as e:
        logger.exception("[ERROR] Unexpected exception while trying to connect: %s", e)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Customer stopped by user.")