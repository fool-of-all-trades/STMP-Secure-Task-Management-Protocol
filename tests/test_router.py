from unittest.mock import patch
import pytest

from server.protocol.router import dispatch, ConnectionState


IP = "127.0.0.1"
DUMMY_TOKEN = "session-token-123"
TS = "2026-05-26T12:00:00Z"

def make_msg(msg_type: str, payload: dict = None) -> dict:
    """Tworzy bazowy słownik wiadomości do testów."""
    return {
        "type": msg_type,
        "timestamp": TS,
        "request_id": "req-1",
        "payload": payload or {}
    }


class TestRouterStateValidation:

    def test_accepts_hello_in_connected_state(self):
        """W stanie CONNECTED dozwolone jest tylko HELLO."""
        msg = make_msg("HELLO")
        resp_type, payload, new_state = dispatch(msg, ConnectionState.CONNECTED, IP, None)
        
        assert resp_type == "HELLO_OK"
        assert new_state == ConnectionState.AUTHENTICATED

    def test_rejects_active_commands_in_connected_state(self):
        """Wysłanie PING zanim wyśle się HELLO zwraca błąd."""
        msg = make_msg("PING")
        resp_type, payload, new_state = dispatch(msg, ConnectionState.CONNECTED, IP, None)
        
        assert resp_type == "ERROR"
        assert payload["error_code"] == 101
        assert "Expected HELLO" in payload["message"]
        assert new_state is None 

    def test_rejects_tasks_in_authenticated_state(self):
        """W stanie AUTHENTICATED nie można tworzyć zadań."""
        msg = make_msg("CREATE_TASK", {"title": "Test"})
        resp_type, payload, new_state = dispatch(msg, ConnectionState.AUTHENTICATED, IP, None)
        
        assert resp_type == "ERROR"
        assert payload["error_code"] == 101
        assert "Expected LOGIN or REGISTER" in payload["message"]

    def test_rejects_unknown_command(self):
        """Router zwraca błąd dla nieznanych typów wiadomości, jeśli jakoś przejdą parser."""
        msg = make_msg("MAGIC_COMMAND")
        with patch("server.protocol.router.STATE_ALLOWED", {ConnectionState.ACTIVE: {"MAGIC_COMMAND"}}):
            resp_type, payload, new_state = dispatch(msg, ConnectionState.ACTIVE, IP, DUMMY_TOKEN)
            
            assert resp_type == "ERROR"
            assert payload["error_code"] == 101
            assert "Unknown message type" in payload["message"]


class TestAuthHandlers:

    @patch("server.protocol.router.register_user")
    def test_register_success(self, mock_register):
        """Poprawna rejestracja nie zmienia stanu bo wymaga logowania."""
        mock_register.return_value = {"ok": True, "user_id": 99}
        
        msg = make_msg("REGISTER", {"username": "admin", "password": "123"})
        resp_type, payload, new_state = dispatch(msg, ConnectionState.AUTHENTICATED, IP, None)
        
        assert resp_type == "REGISTER_OK"
        assert payload["user_id"] == 99
        assert new_state is None
        mock_register.assert_called_once_with("admin", "123", IP)

    @patch("server.protocol.router.login_user")
    def test_login_success(self, mock_login):
        """Poprawne logowanie przełącza stan na ACTIVE."""
        mock_login.return_value = {
            "ok": True, 
            "session_token": DUMMY_TOKEN, 
            "user_id": 1, 
            "expires_at": "2026-05-27T12:00:00Z"
        }
        
        msg = make_msg("LOGIN", {"username": "admin", "password": "123"})
        resp_type, payload, new_state = dispatch(msg, ConnectionState.AUTHENTICATED, IP, None)
        
        assert resp_type == "LOGIN_OK"
        assert payload["session_token"] == DUMMY_TOKEN
        assert new_state == ConnectionState.ACTIVE

    def test_login_missing_credentials(self):
        """Brak hasła podczas logowania zwraca błąd walidacji."""
        msg = make_msg("LOGIN", {"username": "admin"})
        resp_type, payload, new_state = dispatch(msg, ConnectionState.AUTHENTICATED, IP, None)
        
        assert resp_type == "ERROR"
        assert payload["error_code"] == 103


class TestTaskHandlersAndGuard:

    @pytest.fixture(autouse=True)
    def setup_guards(self):
        """Automatycznie przepuszcza timestamp i rate limit we wszystkich testach w tej klasie."""
        with patch("server.protocol.router.validate_message_timestamp", return_value={"ok": True}):
            with patch("server.protocol.router.check_rate_limit", return_value={"ok": True}):
                yield

    @patch("server.protocol.router.create_task")
    def test_create_task_success(self, mock_create):
        """Poprawne utworzenie zadania."""
        mock_create.return_value = {"ok": True, "task": {"id": "t-1", "title": "Kup mleko"}}
        
        msg = make_msg("CREATE_TASK", {"title": "Kup mleko"})
        resp_type, payload, new_state = dispatch(msg, ConnectionState.ACTIVE, IP, DUMMY_TOKEN)
        
        assert resp_type == "TASK_CREATED"
        assert payload["task"]["id"] == "t-1"
        assert new_state is None

    @patch("server.protocol.router.delete_task")
    def test_delete_task_missing_id(self, mock_delete):
        """Próba usunięcia bez podania ID zwraca błąd i nie wywołuje serwisu."""
        msg = make_msg("DELETE_TASK", {})
        resp_type, payload, new_state = dispatch(msg, ConnectionState.ACTIVE, IP, DUMMY_TOKEN)
        
        assert resp_type == "ERROR"
        assert payload["error_code"] == 103
        mock_delete.assert_not_called()

    @patch("server.protocol.router.validate_message_timestamp", return_value={"ok": True})
    @patch("server.protocol.router.check_rate_limit")
    def test_guard_blocks_rate_limit(self, mock_rl, mock_ts):
        """Jeśli serwis rate limitu zwróci błąd, router natychmiast go przekazuje."""
        mock_rl.return_value = {"ok": False, "error_code": 429, "message": "Too many requests"}
        
        msg = make_msg("CREATE_TASK", {"title": "Kup mleko"})
        resp_type, payload, new_state = dispatch(msg, ConnectionState.ACTIVE, IP, DUMMY_TOKEN)
        
        assert resp_type == "ERROR"
        assert payload["error_code"] == 429
        assert "Too many requests" in payload["message"]