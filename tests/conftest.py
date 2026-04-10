import uuid

import pytest

from server.services.auth_service import login_user, logout_user, register_user
from tests.tests_utils import (
    TEST_CLIENT_IP,
    TEST_PASSWORD,
    cleanup_auth_logs_for_user_id,
    cleanup_auth_logs_for_username,
    cleanup_test_user,
)


@pytest.fixture
def unique_username():
    username = f"test_user_{uuid.uuid4().hex[:8]}"
    cleanup_test_user(username)
    yield username
    cleanup_test_user(username)


@pytest.fixture
def registered_user(unique_username):
    register_result = register_user(unique_username, TEST_PASSWORD, TEST_CLIENT_IP)
    assert register_result["ok"] is True

    return {
        "username": unique_username,
        "user_id": register_result["user_id"],
    }


@pytest.fixture
def logged_in_user(registered_user):
    login_result = login_user(
        registered_user["username"],
        TEST_PASSWORD,
        TEST_CLIENT_IP,
    )
    assert login_result["ok"] is True

    yield {
        **registered_user,
        "session_token": login_result["session_token"],
    }

    logout_user(login_result["session_token"])


@pytest.fixture
def auth_log_username(unique_username):
    cleanup_auth_logs_for_username(unique_username)
    yield unique_username
    cleanup_auth_logs_for_username(unique_username)


@pytest.fixture
def registered_user_with_clean_auth_logs(auth_log_username):
    register_result = register_user(auth_log_username, TEST_PASSWORD, TEST_CLIENT_IP)
    assert register_result["ok"] is True

    yield {
        "username": auth_log_username,
        "user_id": register_result["user_id"],
    }

    cleanup_auth_logs_for_user_id(register_result["user_id"])


@pytest.fixture
def logged_in_user_with_clean_auth_logs(registered_user_with_clean_auth_logs):
    login_result = login_user(
        registered_user_with_clean_auth_logs["username"],
        TEST_PASSWORD,
        TEST_CLIENT_IP,
    )
    assert login_result["ok"] is True

    yield {
        **registered_user_with_clean_auth_logs,
        "session_token": login_result["session_token"],
    }

    logout_user(login_result["session_token"])
