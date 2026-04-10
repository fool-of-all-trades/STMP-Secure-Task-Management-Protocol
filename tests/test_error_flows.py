import uuid

from server.services.auth_service import login_user, register_user
from server.services.task_service import create_task, delete_task, update_task
from tests.tests_utils import TEST_CLIENT_IP, TEST_PASSWORD, cleanup_test_user



def test_login_with_wrong_password(registered_user):
    login_result = login_user(
        registered_user["username"],
        "TotallyWrongPassword!",
        TEST_CLIENT_IP,
    )
    assert login_result["ok"] is False
    assert login_result["error_code"] == 200



def test_register_duplicate_user(unique_username):
    first_result = register_user(unique_username, TEST_PASSWORD, TEST_CLIENT_IP)
    second_result = register_user(unique_username, TEST_PASSWORD, TEST_CLIENT_IP)

    assert first_result["ok"] is True
    assert second_result["ok"] is False
    assert second_result["error_code"] == 204



def test_create_task_with_empty_title(logged_in_user):
    create_result = create_task(
        session_token=logged_in_user["session_token"],
        title="",
        description="Should fail",
        status="todo",
    )

    assert create_result["ok"] is False
    assert create_result["error_code"] == 105



def test_create_task_with_invalid_status(logged_in_user):
    create_result = create_task(
        session_token=logged_in_user["session_token"],
        title="Task with bad status",
        description="Should fail",
        status="in_progress",
    )

    assert create_result["ok"] is False
    assert create_result["error_code"] == 104



def test_update_nonexistent_task(logged_in_user):
    fake_task_id = "00000000-0000-0000-0000-000000000000"

    update_result = update_task(
        session_token=logged_in_user["session_token"],
        task_id=fake_task_id,
        title="Updated title",
        description="Updated description",
        status="done",
    )

    assert update_result["ok"] is False
    assert update_result["error_code"] == 300



def test_delete_nonexistent_task(logged_in_user):
    fake_task_id = "00000000-0000-0000-0000-000000000000"

    delete_result = delete_task(logged_in_user["session_token"], fake_task_id)

    assert delete_result["ok"] is False
    assert delete_result["error_code"] == 300



def test_access_denied_on_other_users_task():
    username_1 = f"user_a_{uuid.uuid4().hex[:8]}"
    username_2 = f"user_b_{uuid.uuid4().hex[:8]}"

    cleanup_test_user(username_1)
    cleanup_test_user(username_2)

    register_user(username_1, TEST_PASSWORD, TEST_CLIENT_IP)
    register_user(username_2, TEST_PASSWORD, TEST_CLIENT_IP)

    login_result_1 = login_user(username_1, TEST_PASSWORD, TEST_CLIENT_IP)
    login_result_2 = login_user(username_2, TEST_PASSWORD, TEST_CLIENT_IP)

    session_token_1 = login_result_1["session_token"]
    session_token_2 = login_result_2["session_token"]

    create_result = create_task(
        session_token=session_token_1,
        title="Private task",
        description="Owned by user 1",
        status="todo",
    )
    assert create_result["ok"] is True

    task_id = create_result["task"]["id"]

    update_result = update_task(
        session_token=session_token_2,
        task_id=task_id,
        title="Hacked task",
        description="Should not work",
        status="done",
    )

    assert update_result["ok"] is False
    assert update_result["error_code"] == 203

    delete_result = delete_task(session_token_2, task_id)
    assert delete_result["ok"] is False
    assert delete_result["error_code"] == 203

    cleanup_test_user(username_1)
    cleanup_test_user(username_2)
