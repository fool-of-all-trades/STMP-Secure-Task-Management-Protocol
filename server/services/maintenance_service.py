from datetime import datetime, timezone

from server.db.db import get_connection
from server.db.repositories.maintenance_repository import (
    delete_expired_request_history,
    delete_expired_sessions,
)


def cleanup_expired_security_data() -> dict:
    now = datetime.now(timezone.utc)

    with get_connection() as conn:
        try:
            deleted_sessions = delete_expired_sessions(conn, now)
            deleted_request_history = delete_expired_request_history(conn, now)
            conn.commit()

            return {
                "ok": True,
                "deleted_sessions": deleted_sessions,
                "deleted_request_history": deleted_request_history,
            }
        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}
