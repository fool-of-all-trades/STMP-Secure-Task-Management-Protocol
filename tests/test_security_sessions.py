from server.services.auth_service import login_user, logout_user
from server.server import _mark_session_disconnected_for_reconnect
import uuid
from datetime import datetime, timezone

from server.protocol.router import ConnectionState, dispatch
from server.services.session_service import (
    mark_session_as_disconnected,
    resume_session,
    validate_session,
)
from server.services.task_service import create_task
from tests.tests_utils import (
    TEST_CLIENT_IP,
    TEST_OTHER_CLIENT_IP,
    expire_resume_window,
    expire_session_token,
)


def _make_router_msg(msg_type: str, payload: dict | None = None) -> dict:
    return {
        "type": msg_type,
        "version": "1.0",
        "request_id": f"req-{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": payload or {},
    }


def test_account_lockout_after_failed_logins(registered_user):
    username = registered_user["username"]

    for _ in range(5):
        failed_login = login_user(username, "WrongPassword123!", TEST_CLIENT_IP)
        assert failed_login["ok"] is False
        assert failed_login["error_code"] == 200

    locked_login = login_user(username, "TestPassword123!", TEST_CLIENT_IP)
    assert locked_login["ok"] is False
    assert locked_login["error_code"] == 203
    assert locked_login["message"] == "Account temporarily locked"


def test_session_validation_accepts_original_client_ip(logged_in_user):
    validate_result = validate_session(logged_in_user["session_token"], TEST_CLIENT_IP)

    assert validate_result["ok"] is True
    assert validate_result["user_id"] == logged_in_user["user_id"]


def test_session_validation_rejects_changed_client_ip(logged_in_user):
    validate_result = validate_session(logged_in_user["session_token"], TEST_OTHER_CLIENT_IP)

    assert validate_result["ok"] is False
    assert validate_result["error_code"] == 202


def test_resume_session_rejects_changed_client_ip(logged_in_user):
    session_token = logged_in_user["session_token"]

    disconnected_result = mark_session_as_disconnected(session_token)
    assert disconnected_result["ok"] is True

    resume_result = resume_session(session_token, TEST_OTHER_CLIENT_IP)

    assert resume_result["ok"] is False
    assert resume_result["error_code"] == 202


def test_task_operation_rejects_session_from_changed_client_ip(logged_in_user):
    create_result = create_task(
        session_token=logged_in_user["session_token"],
        title="Wrong IP task",
        description="Should not be created",
        status="todo",
        client_ip=TEST_OTHER_CLIENT_IP,
    )

    assert create_result["ok"] is False
    assert create_result["error_code"] == 202


def test_server_unexpected_disconnect_marks_active_session_for_resume(logged_in_user):
    session_token = logged_in_user["session_token"]

    disconnect_result = _mark_session_disconnected_for_reconnect(
        session_token,
        ConnectionState.ACTIVE,
        graceful_close=False,
        ip=TEST_CLIENT_IP,
    )
    assert disconnect_result is not None
    assert disconnect_result["ok"] is True
    assert "resume_until" in disconnect_result

    resume_result = resume_session(session_token, TEST_CLIENT_IP)
    assert resume_result["ok"] is True
    assert resume_result["message"] == "Session resumed"


def test_reconnect_flow_hello_then_resume_after_unexpected_disconnect(logged_in_user):
    session_token = logged_in_user["session_token"]

    disconnect_result = _mark_session_disconnected_for_reconnect(
        session_token,
        ConnectionState.ACTIVE,
        graceful_close=False,
        ip=TEST_CLIENT_IP,
    )
    assert disconnect_result is not None
    assert disconnect_result["ok"] is True

    hello_type, _, state_after_hello = dispatch(
        _make_router_msg("HELLO"),
        ConnectionState.CONNECTED,
        TEST_CLIENT_IP,
        None,
    )
    assert hello_type == "HELLO_OK"
    assert state_after_hello == ConnectionState.AUTHENTICATED

    resume_type, resume_payload, new_state = dispatch(
        _make_router_msg("RESUME_SESSION", {"session_token": session_token}),
        state_after_hello,
        TEST_CLIENT_IP,
        None,
    )

    assert resume_type == "RESUME_SESSION_OK"
    assert resume_payload["message"] == "Session resumed"
    assert new_state == ConnectionState.ACTIVE


def test_server_graceful_close_does_not_mark_session_for_resume(logged_in_user):
    session_token = logged_in_user["session_token"]

    logout_result = logout_user(session_token)
    assert logout_result["ok"] is True

    disconnect_result = _mark_session_disconnected_for_reconnect(
        session_token,
        ConnectionState.DISCONNECTED,
        graceful_close=True,
        ip=TEST_CLIENT_IP,
    )
    assert disconnect_result is None

    resume_result = resume_session(session_token, TEST_CLIENT_IP)
    assert resume_result["ok"] is False
    assert resume_result["error_code"] == 202


def test_revoked_session_cannot_be_validated_or_resumed(logged_in_user):
    session_token = logged_in_user["session_token"]

    logout_result = logout_user(session_token)
    assert logout_result["ok"] is True

    validate_result = validate_session(session_token, TEST_CLIENT_IP)
    assert validate_result["ok"] is False
    assert validate_result["error_code"] == 202

    resume_result = resume_session(session_token, TEST_CLIENT_IP)
    assert resume_result["ok"] is False
    assert resume_result["error_code"] == 202


def test_resume_session_success_after_disconnect(logged_in_user):
    session_token = logged_in_user["session_token"]

    disconnected_result = mark_session_as_disconnected(session_token)
    assert disconnected_result["ok"] is True
    assert "resume_until" in disconnected_result

    resume_result = resume_session(session_token, TEST_CLIENT_IP)
    assert resume_result["ok"] is True
    assert resume_result["message"] == "Session resumed"

    validate_result = validate_session(session_token, TEST_CLIENT_IP)
    assert validate_result["ok"] is True
    assert validate_result["user_id"] == logged_in_user["user_id"]



def test_resume_session_fails_after_resume_window_expires(logged_in_user):
    session_token = logged_in_user["session_token"]

    disconnected_result = mark_session_as_disconnected(session_token)
    assert disconnected_result["ok"] is True

    expire_resume_window(session_token)

    resume_result = resume_session(session_token, TEST_CLIENT_IP)
    assert resume_result["ok"] is False
    assert resume_result["error_code"] == 202



def test_session_expired_is_rejected_by_validation_and_resume(logged_in_user):
    session_token = logged_in_user["session_token"]

    expire_session_token(session_token)

    validate_result = validate_session(session_token, TEST_CLIENT_IP)
    assert validate_result["ok"] is False
    assert validate_result["error_code"] == 202

    resume_result = resume_session(session_token, TEST_CLIENT_IP)
    assert resume_result["ok"] is False
    assert resume_result["error_code"] == 202
