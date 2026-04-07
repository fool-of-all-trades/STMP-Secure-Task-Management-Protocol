from datetime import datetime, timedelta, timezone
from uuid import UUID

from server.db.db import get_connection
from server.security.security_utils import hash_password, verify_password, generate_session_token, hash_token


def authorize_task_access(user_id: str, task_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM tasks
                WHERE id = %s AND user_id = %s
                """,
                (task_id, user_id)
            )
            return cur.fetchone() is not None

