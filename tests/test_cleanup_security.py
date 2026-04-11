import uuid

from server.services.auth_service import login_user, register_user
from server.services.maintenance_service import cleanup_expired_security_data
from server.services.session_service import validate_session
from tests.tests_utils import (
    TEST_CLIENT_IP,
    TEST_PASSWORD,
    cleanup_request_history,
    cleanup_test_user,
    count_request_history_records,
    count_session_records,
    expire_session_token,
    insert_request_history_record,
)


def test_cleanup_removes_only_expired_sessions():
    username = f"cleanup_sessions_{uuid.uuid4().hex[:8]}"
    cleanup_test_user(username)

    register_user(username, TEST_PASSWORD, TEST_CLIENT_IP)

    expired_login = login_user(username, TEST_PASSWORD, TEST_CLIENT_IP)
    active_login = login_user(username, TEST_PASSWORD, TEST_CLIENT_IP)

    assert expired_login["ok"] is True
    assert active_login["ok"] is True

    expired_token = expired_login["session_token"]
    active_token = active_login["session_token"]

    expire_session_token(expired_token)

    assert count_session_records(expired_token) == 1
    assert count_session_records(active_token) == 1

    cleanup_result = cleanup_expired_security_data()
    assert cleanup_result["ok"] is True
    assert cleanup_result["deleted_sessions"] >= 1

    assert count_session_records(expired_token) == 0
    assert count_session_records(active_token) == 1

    active_validation = validate_session(active_token, TEST_CLIENT_IP)
    assert active_validation["ok"] is True

    cleanup_test_user(username)



def test_cleanup_removes_only_expired_request_history():
    scope_key = f"test-scope-{uuid.uuid4().hex[:8]}"
    expired_request_id = f"expired-{uuid.uuid4().hex[:8]}"
    active_request_id = f"active-{uuid.uuid4().hex[:8]}"

    cleanup_request_history(scope_key)

    insert_request_history_record(
        scope_key=scope_key,
        request_id=expired_request_id,
        expires_in_seconds=-60,
    )
    insert_request_history_record(
        scope_key=scope_key,
        request_id=active_request_id,
        expires_in_seconds=300,
    )

    assert count_request_history_records(scope_key, expired_request_id) == 1
    assert count_request_history_records(scope_key, active_request_id) == 1

    cleanup_result = cleanup_expired_security_data()
    assert cleanup_result["ok"] is True
    assert cleanup_result["deleted_request_history"] >= 1

    assert count_request_history_records(scope_key, expired_request_id) == 0
    assert count_request_history_records(scope_key, active_request_id) == 1

    cleanup_request_history(scope_key)
