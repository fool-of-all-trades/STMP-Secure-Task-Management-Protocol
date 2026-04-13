from server.services.auth_service import login_user, logout_user
from server.services.session_service import (
    mark_session_as_disconnected,
    resume_session,
    validate_session,
)
from tests.tests_utils import TEST_CLIENT_IP, expire_resume_window, expire_session_token


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
