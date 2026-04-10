from server.services.auth_service import logout_user
from server.services.session_service import validate_session
from tests.tests_utils import TEST_CLIENT_IP


def test_auth_flow(logged_in_user):
    validate_result = validate_session(logged_in_user["session_token"], TEST_CLIENT_IP)
    assert validate_result["ok"] is True
    assert validate_result["user_id"] == logged_in_user["user_id"]

    logout_result = logout_user(logged_in_user["session_token"])
    assert logout_result["ok"] is True

    validate_after_logout = validate_session(logged_in_user["session_token"], TEST_CLIENT_IP)
    assert validate_after_logout["ok"] is False
    assert validate_after_logout["error_code"] == 202
