from server.services.auth_service import login_user, logout_user, register_user
from tests.tests_utils import (
    TEST_CLIENT_IP,
    TEST_PASSWORD,
    fetch_auth_logs_by_username,
    get_latest_auth_log_by_user_id,
    get_latest_auth_log_by_username,
)



def test_register_success_writes_auth_log(auth_log_username):
    register_result = register_user(auth_log_username, TEST_PASSWORD, TEST_CLIENT_IP)
    assert register_result["ok"] is True

    log_entry = get_latest_auth_log_by_username(auth_log_username, "REGISTER")
    assert log_entry is not None
    assert log_entry["username_attempted"] == auth_log_username
    assert log_entry["user_id"] == register_result["user_id"]
    assert log_entry["client_ip"] == TEST_CLIENT_IP
    assert log_entry["event_type"] == "REGISTER"
    assert log_entry["success"] is True
    assert log_entry["error_code"] is None



def test_register_duplicate_writes_failed_auth_log(auth_log_username):
    first_result = register_user(auth_log_username, TEST_PASSWORD, TEST_CLIENT_IP)
    second_result = register_user(auth_log_username, TEST_PASSWORD, TEST_CLIENT_IP)

    assert first_result["ok"] is True
    assert second_result["ok"] is False
    assert second_result["error_code"] == 204

    logs = fetch_auth_logs_by_username(auth_log_username, "REGISTER")
    assert len(logs) >= 2

    last_log = logs[-1]
    assert last_log["username_attempted"] == auth_log_username
    assert last_log["client_ip"] == TEST_CLIENT_IP
    assert last_log["event_type"] == "REGISTER"
    assert last_log["success"] is False
    assert last_log["error_code"] == 204



def test_login_wrong_password_writes_failed_auth_log(registered_user_with_clean_auth_logs):
    login_result = login_user(
        registered_user_with_clean_auth_logs["username"],
        "WrongPassword123!",
        TEST_CLIENT_IP,
    )

    assert login_result["ok"] is False
    assert login_result["error_code"] == 200

    log_entry = get_latest_auth_log_by_username(
        registered_user_with_clean_auth_logs["username"],
        "LOGIN",
    )
    assert log_entry is not None
    assert log_entry["username_attempted"] == registered_user_with_clean_auth_logs["username"]
    assert log_entry["user_id"] == registered_user_with_clean_auth_logs["user_id"]
    assert log_entry["client_ip"] == TEST_CLIENT_IP
    assert log_entry["event_type"] == "LOGIN"
    assert log_entry["success"] is False
    assert log_entry["error_code"] == 200



def test_login_unknown_user_writes_failed_auth_log_without_user_id(auth_log_username):
    login_result = login_user(auth_log_username, "WrongPassword123!", TEST_CLIENT_IP)

    assert login_result["ok"] is False
    assert login_result["error_code"] == 200

    log_entry = get_latest_auth_log_by_username(auth_log_username, "LOGIN")
    assert log_entry is not None
    assert log_entry["username_attempted"] == auth_log_username
    assert log_entry["user_id"] is None
    assert log_entry["client_ip"] == TEST_CLIENT_IP
    assert log_entry["event_type"] == "LOGIN"
    assert log_entry["success"] is False
    assert log_entry["error_code"] == 200



def test_successful_login_and_logout_write_auth_logs(logged_in_user_with_clean_auth_logs):
    login_log = get_latest_auth_log_by_username(
        logged_in_user_with_clean_auth_logs["username"],
        "LOGIN",
    )
    assert login_log is not None
    assert login_log["user_id"] == logged_in_user_with_clean_auth_logs["user_id"]
    assert login_log["client_ip"] == TEST_CLIENT_IP
    assert login_log["success"] is True
    assert login_log["error_code"] is None

    logout_result = logout_user(logged_in_user_with_clean_auth_logs["session_token"])
    assert logout_result["ok"] is True

    logout_log = get_latest_auth_log_by_user_id(
        logged_in_user_with_clean_auth_logs["user_id"],
        "LOGOUT",
    )
    assert logout_log is not None
    assert logout_log["username_attempted"] is None
    assert logout_log["user_id"] == logged_in_user_with_clean_auth_logs["user_id"]
    assert logout_log["client_ip"] is None
    assert logout_log["event_type"] == "LOGOUT"
    assert logout_log["success"] is True
    assert logout_log["error_code"] is None



def test_account_lockout_writes_203_auth_log(registered_user_with_clean_auth_logs):
    username = registered_user_with_clean_auth_logs["username"]

    for _ in range(5):
        failed_login = login_user(username, "WrongPassword123!", TEST_CLIENT_IP)
        assert failed_login["ok"] is False
        assert failed_login["error_code"] == 200

    locked_login = login_user(username, TEST_PASSWORD, TEST_CLIENT_IP)
    assert locked_login["ok"] is False
    assert locked_login["error_code"] == 203

    log_entry = get_latest_auth_log_by_username(username, "LOGIN")
    assert log_entry is not None
    assert log_entry["username_attempted"] == username
    assert log_entry["user_id"] == registered_user_with_clean_auth_logs["user_id"]
    assert log_entry["client_ip"] == TEST_CLIENT_IP
    assert log_entry["event_type"] == "LOGIN"
    assert log_entry["success"] is False
    assert log_entry["error_code"] == 203



def test_auth_logs_do_not_contain_password_or_session_token(logged_in_user_with_clean_auth_logs):
    logs = fetch_auth_logs_by_username(logged_in_user_with_clean_auth_logs["username"])
    serialized_logs = "\n".join(str(log) for log in logs)

    assert TEST_PASSWORD not in serialized_logs
    assert logged_in_user_with_clean_auth_logs["session_token"] not in serialized_logs
