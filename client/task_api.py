import logging

from .protocol import MsgType

logger = logging.getLogger("task_api")


class TaskAPI:
    # Dodanie nowego zadania
    async def create_task(self, title: str, description: str, status: str) -> dict:
        payload = {"title": title, "description": description, "status": status}
        try:
            resp = await self.request(MsgType.CREATE_TASK, payload)
            if resp.get("type") == MsgType.TASK_CREATED:
                return {"success": True, "message": "Zadanie utworzone pomyślnie."}
            error = resp.get("payload", {}).get("message", "Nie udało się utworzyć zadania.")
            return {"success": False, "message": error}
        except Exception as e:
            return {"success": False, "message": f"Błąd sieci: {e}"}

    # Edycja wybranego zadania
    async def update_task(
        self, task_id: str, title: str, description: str, status: str
    ) -> dict:
        payload = {
            "task_id":     task_id,
            "title":       title,
            "description": description,
            "status":      status,
        }
        try:
            resp = await self.request(MsgType.UPDATE_TASK, payload)
            if resp.get("type") == MsgType.TASK_UPDATED:
                return {"success": True, "message": "Zadanie zaktualizowane pomyślnie."}
            error = resp.get("payload", {}).get("message", "Nie udało się zaktualizować zadania.")
            return {"success": False, "message": error}
        except Exception as e:
            return {"success": False, "message": f"Błąd sieci: {e}"}

    # Usunięcie zadania z listy
    async def delete_task(self, task_id: str) -> dict:
        payload = {"task_id": task_id}
        try:
            resp = await self.request(MsgType.DELETE_TASK, payload)
            if resp.get("type") == MsgType.TASK_DELETED:
                return {"success": True, "message": "Zadanie usunięte pomyślnie."}
            error = resp.get("payload", {}).get("message", "Nie udało się usunąć zadania.")
            return {"success": False, "message": error}
        except Exception as e:
            return {"success": False, "message": f"Błąd sieci: {e}"}