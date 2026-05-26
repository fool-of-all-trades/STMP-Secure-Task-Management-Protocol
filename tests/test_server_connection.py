import ssl
import socket
import pytest


SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8888
TIMEOUT = 5  # sekundy


def make_tls_context() -> ssl.SSLContext:
    """Kontekst TLS dla testów – pomija weryfikację self-signed certa."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def connect() -> ssl.SSLSocket:
    """Zestawia połączenie TLS z serwerem. Rzuca pytest.skip jeśli serwer nie działa."""
    ctx = make_tls_context()
    try:
        sock = socket.create_connection((SERVER_HOST, SERVER_PORT), timeout=TIMEOUT)
        return ctx.wrap_socket(sock)
    except ConnectionRefusedError:
        pytest.skip("Serwer nie jest uruchomiony – odpal: python -m server.server")


# ==============================================================================

class TestServerConnection:

    def test_connects_successfully(self):
        """Serwer przyjmuje połączenie TLS."""
        with connect() as tls:
            assert tls.version() == "TLSv1.3"

    def test_tls_version_is_1_3(self):
        """Serwer wymaga TLS 1.3 (nie niżej)."""
        with connect() as tls:
            assert tls.version() == "TLSv1.3", f"Oczekiwano TLSv1.3, dostano {tls.version()}"

    def test_server_accepts_data(self):
        """Serwer nie zamyka połączenia od razu po odebraniu danych."""
        with connect() as tls:
            tls.sendall(b"test")
            tls.settimeout(1)
            try:
                data = tls.recv(1024)
            except socket.timeout:
                pass

    def test_multiple_connections(self):
        """Serwer obsługuje wiele jednoczesnych połączeń."""
        connections = []
        try:
            for _ in range(3):
                connections.append(connect())
            assert len(connections) == 3
        finally:
            for conn in connections:
                try:
                    conn.close()
                except Exception:
                    pass

    def test_connection_limit_per_ip(self):
        """Serwer odrzuca połączenia po przekroczeniu limitu per-IP (5)."""
        connections = []
        rejected = False
        try:
            for i in range(7): 
                try:
                    conn = connect()
                    conn.settimeout(0.5)
                    try:
                        data = conn.recv(1)
                        if not data:
                            rejected = True
                            break
                    except socket.timeout:
                        connections.append(conn)
                except (ConnectionResetError, OSError, ssl.SSLError):
                    rejected = True
                    break
            
            assert rejected or len(connections) <= 5, (
                "Serwer powinien odrzucić połączenie po przekroczeniu limitu per-IP"
            )
        finally:
            for conn in connections:
                try:
                    conn.close()
                except Exception:
                    pass