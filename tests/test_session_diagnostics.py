from server.services.auth_service import logout_user
from server.services.session_service import (
    mark_session_as_disconnected,
    resume_session,
    validate_session,
)
from tests.tests_utils import (
    TEST_CLIENT_IP,
    expire_resume_window,
    expire_session_token,
    get_latest_auth_log_by_user_id,
)


def test_validate_session_success_writes_log(logged_in_user_with_clean_auth_logs):
    validate_result = validate_session(
        logged_in_user_with_clean_auth_logs["session_token"],
        TEST_CLIENT_IP,
    )
    assert validate_result["ok"] is True

    log_entry = get_latest_auth_log_by_user_id(
        logged_in_user_with_clean_auth_logs["user_id"],
        "SESSION_VALIDATE",
    )
    assert log_entry is not None
    assert log_entry["username_attempted"] is None
    assert log_entry["user_id"] == logged_in_user_with_clean_auth_logs["user_id"]
    assert log_entry["client_ip"] == TEST_CLIENT_IP
    assert log_entry["event_type"] == "SESSION_VALIDATE"
    assert log_entry["success"] is True
    assert log_entry["error_code"] is None



def test_validate_expired_session_writes_failed_log(logged_in_user_with_clean_auth_logs):
    session_token = logged_in_user_with_clean_auth_logs["session_token"]
    expire_session_token(session_token)

    validate_result = validate_session(session_token, TEST_CLIENT_IP)
    assert validate_result["ok"] is False
    assert validate_result["error_code"] == 202

    log_entry = get_latest_auth_log_by_user_id(
        logged_in_user_with_clean_auth_logs["user_id"],
        "SESSION_VALIDATE",
    )
    assert log_entry is not None
    assert log_entry["user_id"] == logged_in_user_with_clean_auth_logs["user_id"]
    assert log_entry["client_ip"] == TEST_CLIENT_IP
    assert log_entry["event_type"] == "SESSION_VALIDATE"
    assert log_entry["success"] is False
    assert log_entry["error_code"] == 202



def test_mark_session_as_disconnected_writes_log(logged_in_user_with_clean_auth_logs):
    disconnect_result = mark_session_as_disconnected(
        logged_in_user_with_clean_auth_logs["session_token"]
    )
    assert disconnect_result["ok"] is True

    log_entry = get_latest_auth_log_by_user_id(
        logged_in_user_with_clean_auth_logs["user_id"],
        "SESSION_DISCONNECT",
    )
    assert log_entry is not None
    assert log_entry["user_id"] == logged_in_user_with_clean_auth_logs["user_id"]
    assert log_entry["client_ip"] == TEST_CLIENT_IP
    assert log_entry["event_type"] == "SESSION_DISCONNECT"
    assert log_entry["success"] is True
    assert log_entry["error_code"] is None



def test_resume_session_success_writes_log(logged_in_user_with_clean_auth_logs):
    session_token = logged_in_user_with_clean_auth_logs["session_token"]

    disconnect_result = mark_session_as_disconnected(session_token)
    assert disconnect_result["ok"] is True

    resume_result = resume_session(session_token, TEST_CLIENT_IP)
    assert resume_result["ok"] is True

    log_entry = get_latest_auth_log_by_user_id(
        logged_in_user_with_clean_auth_logs["user_id"],
        "SESSION_RESUME",
    )
    assert log_entry is not None
    assert log_entry["user_id"] == logged_in_user_with_clean_auth_logs["user_id"]
    assert log_entry["client_ip"] == TEST_CLIENT_IP
    assert log_entry["event_type"] == "SESSION_RESUME"
    assert log_entry["success"] is True
    assert log_entry["error_code"] is None



def test_resume_session_expired_window_writes_failed_log(logged_in_user_with_clean_auth_logs):
    session_token = logged_in_user_with_clean_auth_logs["session_token"]

    disconnect_result = mark_session_as_disconnected(session_token)
    assert disconnect_result["ok"] is True

    expire_resume_window(session_token)

    resume_result = resume_session(session_token, TEST_CLIENT_IP)
    assert resume_result["ok"] is False
    assert resume_result["error_code"] == 202

    log_entry = get_latest_auth_log_by_user_id(
        logged_in_user_with_clean_auth_logs["user_id"],
        "SESSION_RESUME",
    )
    assert log_entry is not None
    assert log_entry["user_id"] == logged_in_user_with_clean_auth_logs["user_id"]
    assert log_entry["client_ip"] == TEST_CLIENT_IP
    assert log_entry["event_type"] == "SESSION_RESUME"
    assert log_entry["success"] is False
    assert log_entry["error_code"] == 202



def test_revoked_session_validate_and_resume_write_failed_logs(logged_in_user_with_clean_auth_logs):
    session_token = logged_in_user_with_clean_auth_logs["session_token"]

    logout_result = logout_user(session_token)
    assert logout_result["ok"] is True

    validate_result = validate_session(session_token, TEST_CLIENT_IP)
    assert validate_result["ok"] is False
    assert validate_result["error_code"] == 202

    resume_result = resume_session(session_token, TEST_CLIENT_IP)
    assert resume_result["ok"] is False
    assert resume_result["error_code"] == 202

    validate_log = get_latest_auth_log_by_user_id(
        logged_in_user_with_clean_auth_logs["user_id"],
        "SESSION_VALIDATE",
    )
    assert validate_log is not None
    assert validate_log["success"] is False
    assert validate_log["error_code"] == 202

    resume_log = get_latest_auth_log_by_user_id(
        logged_in_user_with_clean_auth_logs["user_id"],
        "SESSION_RESUME",
    )
    assert resume_log is not None
    assert resume_log["success"] is False
    assert resume_log["error_code"] == 202
