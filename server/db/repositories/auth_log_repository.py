from datetime import datetime, timedelta, timezone
from uuid import UUID

from server.db.db import get_connection
from server.security.security_utils import hash_password, verify_password, generate_session_token, hash_token


def log_auth_event(conn, username_attempted, user_id, client_ip, event_type, success, error_code=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO auth_logs (username_attempted, user_id, client_ip, event_type, success, error_code)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (username_attempted, user_id, client_ip, event_type, success, error_code)
        )
