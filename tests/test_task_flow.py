from server.services.auth_service import logout_user
from server.services.task_service import create_task, delete_task, list_tasks, update_task


def test_task_flow(logged_in_user):
    session_token = logged_in_user["session_token"]

    create_result = create_task(
        session_token=session_token,
        title="First task",
        description="Task created in automated test",
        status="todo",
    )
    assert create_result["ok"] is True
    assert "task" in create_result
    assert create_result["task"]["title"] == "First task"
    assert create_result["task"]["status"] == "todo"

    task_id = create_result["task"]["id"]

    list_result = list_tasks(session_token)
    assert list_result["ok"] is True
    assert "tasks" in list_result
    assert len(list_result["tasks"]) >= 1
    assert any(task["id"] == task_id for task in list_result["tasks"])

    update_result = update_task(
        session_token=session_token,
        task_id=task_id,
        title="Updated task",
        description="Updated description",
        status="done",
    )
    assert update_result["ok"] is True
    assert update_result["task"]["id"] == task_id
    assert update_result["task"]["title"] == "Updated task"
    assert update_result["task"]["description"] == "Updated description"
    assert update_result["task"]["status"] == "done"

    list_after_update = list_tasks(session_token)
    assert list_after_update["ok"] is True

    updated_task = next((task for task in list_after_update["tasks"] if task["id"] == task_id), None)
    assert updated_task is not None
    assert updated_task["title"] == "Updated task"
    assert updated_task["description"] == "Updated description"
    assert updated_task["status"] == "done"

    delete_result = delete_task(session_token, task_id)
    assert delete_result["ok"] is True
    assert delete_result["task_id"] == task_id

    list_after_delete = list_tasks(session_token)
    assert list_after_delete["ok"] is True
    assert all(task["id"] != task_id for task in list_after_delete["tasks"])

    logout_result = logout_user(session_token)
    assert logout_result["ok"] is True
