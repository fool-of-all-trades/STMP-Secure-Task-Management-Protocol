import logging
from client.network.protocol import MsgType
from shared.error_codes import ERROR_CODES

logger = logging.getLogger("task_api")


class TaskAPI:
    # Pobranie tekstu na podstawie kodu błędu
    def _get_error_message(self, resp: dict, default_msg: str) -> str:
        payload = resp.get("payload", {})
        error_code = payload.get("error_code")
        if error_code in ERROR_CODES:
            return f"{ERROR_CODES[error_code]} ({payload.get('message', default_msg)})"
        return payload.get("message", default_msg)

    # Dodanie nowego zadania
    async def create_task(self, title: str, description: str, status: str) -> dict:
        payload = {"title": title, "description": description, "status": status}
        try:
            resp = await self.request(MsgType.CREATE_TASK, payload)
            if resp.get("type") == MsgType.TASK_CREATED:
                return {"success": True, "message": "Zadanie utworzone pomyślnie."}

            # Wykorzystanie mapowania kodów błędów
            error = self._get_error_message(resp, "Nie udało się utworzyć zadania.")
            return {"success": False, "message": error}
        except Exception as e:
            return {"success": False, "message": f"Błąd sieci: {e}"}

    # Edycja wybranego zadania
    async def update_task(
            self, task_id: str, title: str, description: str, status: str
    ) -> dict:
        payload = {
            "task_id": task_id,
            "title": title,
            "description": description,
            "status": status,
        }
        try:
            resp = await self.request(MsgType.UPDATE_TASK, payload)
            if resp.get("type") == MsgType.TASK_UPDATED:
                return {"success": True, "message": "Zadanie zaktualizowane pomyślnie."}

            # Wykorzystanie mapowania kodów błędów
            error = self._get_error_message(resp, "Nie udało się zaktualizować zadania.")
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

            # Wykorzystanie mapowania kodów błędów
            error = self._get_error_message(resp, "Nie udało się usunąć zadania.")
            return {"success": False, "message": error}
        except Exception as e:
            return {"success": False, "message": f"Błąd sieci: {e}"}