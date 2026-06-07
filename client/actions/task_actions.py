# Pobranie listy zadań
def fetch_tasks(coordinator):
    future = coordinator.run_async(coordinator.client.request("GET_TASK", {}))
    try:
        response = future.result(timeout=5.0)
        if response.get("type") == "TASK_LIST":
            tasks = response.get("payload", {}).get("tasks", [])
            return {"success": True, "tasks": tasks}
        msg = response.get("payload", {}).get("message", "Failed to fetch tasks.")
        return {"success": False, "message": msg}
    except Exception as e:
        return {"success": False, "message": f"Application error: {str(e)}"}

# Dodanie nowego zadania
def create_task(coordinator, title, description, status):
    if not title:
        return {"success": False, "message": "Task title is required!"}

    future = coordinator.run_async(
        coordinator.client.create_task(title, description, status)
    )
    try:
        return future.result(timeout=5.0)
    except Exception as e:
        return {"success": False, "message": f"Application error: {str(e)}"}

# Zaktualizowanie wybranego zadania
def update_task(coordinator, task_id, title, description, status):
    if not title:
        return {"success": False, "message": "Task title is required!"}

    future = coordinator.run_async(
        coordinator.client.update_task(task_id, title, description, status)
    )
    try:
        return future.result(timeout=5.0)
    except Exception as e:
        return {"success": False, "message": f"Application error: {str(e)}"}

# Usunięcie zadania
def delete_task(coordinator, task_id):
    future = coordinator.run_async(coordinator.client.delete_task(task_id))
    try:
        return future.result(timeout=5.0)
    except Exception as e:
        return {"success": False, "message": f"Application error: {str(e)}"}