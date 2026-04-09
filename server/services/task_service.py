from server.db.db import get_connection
from server.db.repositories.task_repository import (
    create_task as repo_create_task,
    delete_task as repo_delete_task,
    get_task_by_id,
    get_tasks_for_user,
    update_task as repo_update_task,
)
from server.services.session_service import validate_session


ALLOWED_TASK_STATUSES = {"todo", "done"}


def _validate_task_fields(title: str, description: str, status: str) -> dict | None:
    title = title.strip() if title else ""
    description = description if description is not None else ""

    if not title or len(title) > 256:
        return {"ok": False, "error_code": 105, "message": "Invalid task title length"}

    if len(description) > 2048:
        return {"ok": False, "error_code": 105, "message": "Invalid task description length"}

    if status not in ALLOWED_TASK_STATUSES:
        return {"ok": False, "error_code": 104, "message": "Invalid task status"}

    return None


def create_task(session_token: str, title: str, description: str = "", status: str = "todo") -> dict:
    session_result = validate_session(session_token)
    if not session_result["ok"]:
        return session_result

    validation_error = _validate_task_fields(title, description, status)
    if validation_error:
        return validation_error

    user_id = session_result["user_id"]

    with get_connection() as conn:
        try:
            task = repo_create_task(conn, user_id, title.strip(), description, status)
            conn.commit()

            return {
                "ok": True,
                "task": {
                    "id": str(task["id"]),
                    "user_id": str(task["user_id"]),
                    "title": task["title"],
                    "description": task["description"],
                    "status": task["status"],
                    "created_at": task["created_at"].isoformat(),
                    "updated_at": task["updated_at"].isoformat(),
                },
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}


def list_tasks(session_token: str) -> dict:
    session_result = validate_session(session_token)
    if not session_result["ok"]:
        return session_result

    user_id = session_result["user_id"]

    with get_connection() as conn:
        try:
            tasks = get_tasks_for_user(conn, user_id)

            return {
                "ok": True,
                "tasks": [
                    {
                        "id": str(task["id"]),
                        "user_id": str(task["user_id"]),
                        "title": task["title"],
                        "description": task["description"],
                        "status": task["status"],
                        "created_at": task["created_at"].isoformat(),
                        "updated_at": task["updated_at"].isoformat(),
                    }
                    for task in tasks
                ],
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}


def update_task(session_token: str, task_id: str, title: str, description: str = "", status: str = "todo") -> dict:
    session_result = validate_session(session_token)
    if not session_result["ok"]:
        return session_result

    validation_error = _validate_task_fields(title, description, status)
    if validation_error:
        return validation_error

    user_id = session_result["user_id"]

    with get_connection() as conn:
        try:
            existing_task = get_task_by_id(conn, task_id)

            if not existing_task:
                return {"ok": False, "error_code": 300, "message": "Task not found"}

            if str(existing_task["user_id"]) != str(user_id):
                return {"ok": False, "error_code": 203, "message": "Access denied"}

            updated_task = repo_update_task(conn, task_id, title.strip(), description, status)
            conn.commit()

            return {
                "ok": True,
                "task": {
                    "id": str(updated_task["id"]),
                    "user_id": str(updated_task["user_id"]),
                    "title": updated_task["title"],
                    "description": updated_task["description"],
                    "status": updated_task["status"],
                    "created_at": updated_task["created_at"].isoformat(),
                    "updated_at": updated_task["updated_at"].isoformat(),
                },
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}


def delete_task(session_token: str, task_id: str) -> dict:
    session_result = validate_session(session_token)
    if not session_result["ok"]:
        return session_result

    user_id = session_result["user_id"]

    with get_connection() as conn:
        try:
            existing_task = get_task_by_id(conn, task_id)

            if not existing_task:
                return {"ok": False, "error_code": 300, "message": "Task not found"}

            if str(existing_task["user_id"]) != str(user_id):
                return {"ok": False, "error_code": 203, "message": "Access denied"}

            deleted = repo_delete_task(conn, task_id)
            conn.commit()

            if not deleted:
                return {"ok": False, "error_code": 300, "message": "Task not found"}

            return {
                "ok": True,
                "task_id": str(task_id),
                "message": "Task deleted",
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}