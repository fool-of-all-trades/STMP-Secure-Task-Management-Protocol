import json
import socket
import ssl
import time
from datetime import datetime, timezone

import pytest


SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8888
TIMEOUT = 5

IDLE_TIMEOUT = 60


def make_tls_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def connect() -> ssl.SSLSocket:
    ctx = make_tls_context()
    try:
        sock = socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=TIMEOUT)
        return ctx.wrap_socket(sock)
    except ConnectionRefusedError:
        pytest.skip("Serwer nie jest uruchomiony")


def build_frame(msg_type: str, payload: dict, request_id: str = "req-1") -> bytes:
    message = {
        "type": msg_type,
        "version": "1.0",
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": payload,
    }
    json_bytes = json.dumps(message).encode("utf-8")
    size_bytes = len(json_bytes).to_bytes(4, byteorder="big")
    return size_bytes + json_bytes


def read_frame(sock: ssl.SSLSocket, timeout: float = 5) -> dict:
    """Czyta jedna ramke length-prefixed JSON."""
    sock.settimeout(timeout)
    size_bytes = sock.recv(4)
    if len(size_bytes) < 4:
        raise ConnectionError("Incomplete size header")
    size = int.from_bytes(size_bytes, byteorder="big")

    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Connection closed while reading frame")
        data += chunk

    return json.loads(data.decode("utf-8"))


# ==================================================================================

class TestIdleTimeout:

    def test_ping_pong_keeps_connection_alive(self):
        """Klient ktory regularnie wysyla PING – polaczenie pozostaje otwarte."""
        with connect() as tls:
            # HELLO
            tls.sendall(build_frame("HELLO", {}, "req-hello"))
            resp = read_frame(tls)
            assert resp["type"] == "HELLO_OK"

            time.sleep(2)

            tls.sendall(build_frame("PING", {}, "req-ping"))

            resp = read_frame(tls)
            assert resp["type"] in ("PONG", "ERROR")

    @pytest.mark.slow
    def test_idle_client_gets_disconnected(self):
        """
        Klient ktory nic nie wysyla przez IDLE_TIMEOUT sekund
        zostaje rozlaczony przez serwer.

        UWAGA: ten test trwa ~IDLE_TIMEOUT + kilka sekund.
        """
        with connect() as tls:
            tls.sendall(build_frame("HELLO", {}, "req-hello"))
            resp = read_frame(tls)
            assert resp["type"] == "HELLO_OK"

            tls.settimeout(IDLE_TIMEOUT + 10)

            data = tls.recv(1024)
            assert data == b"", (
                f"Oczekiwano zamkniecia polaczenia po {IDLE_TIMEOUT}s bezczynnosci, "
                f"ale serwer wyslal dane: {data!r}"
            )

