from datetime import datetime, timedelta, timezone

from server.db.db import get_connection
from server.security.security_utils import hash_token

TEST_CLIENT_IP = "127.0.0.1"
TEST_PASSWORD = "TestPassword123!"


def cleanup_test_user(username: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s", (username,))
        conn.commit()


def count_session_records(session_token: str) -> int:
    token_hash = hash_token(session_token)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM sessions WHERE token_hash = %s",
                (token_hash,),
            )
            row = cur.fetchone()

    return row[0]


def insert_request_history_record(
    scope_key: str,
    request_id: str,
    message_type: str = "CREATE_TASK",
    request_hash: str = "a" * 64,
    expires_in_seconds: int = 300,
) -> None:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_in_seconds)

    if expires_in_seconds <= 0:
        created_at = expires_at - timedelta(minutes=5)
    else:
        created_at = now

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO request_history (
                    scope_key,
                    request_id,
                    message_type,
                    request_hash,
                    response_code,
                    created_at,
                    expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    scope_key,
                    request_id,
                    message_type,
                    request_hash,
                    None,
                    created_at,
                    expires_at,
                ),
            )
        conn.commit()


def count_request_history_records(scope_key: str, request_id: str) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM request_history
                WHERE scope_key = %s AND request_id = %s
                """,
                (scope_key, request_id),
            )
            row = cur.fetchone()

    return row[0]


def cleanup_request_history(scope_key: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM request_history WHERE scope_key = %s",
                (scope_key,),
            )
        conn.commit()



def expire_session_token(session_token: str, minutes_ago: int = 1) -> None:
    now = datetime.now(timezone.utc)
    expired_at = now - timedelta(minutes=minutes_ago)
    created_at = expired_at - timedelta(minutes=10)
    token_hash = hash_token(session_token)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sessions
                SET created_at = %s,
                    last_seen_at = %s,
                    expires_at = %s
                WHERE token_hash = %s
                """,
                (created_at, expired_at, expired_at, token_hash),
            )
        conn.commit()


def expire_resume_window(session_token: str, minutes_ago: int = 1) -> None:
    now = datetime.now(timezone.utc)
    expired_at = now - timedelta(minutes=minutes_ago)
    created_at = expired_at - timedelta(minutes=10)
    disconnected_at = expired_at - timedelta(minutes=5)
    token_hash = hash_token(session_token)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sessions
                SET created_at = %s,
                    last_seen_at = %s,
                    disconnected_at = %s,
                    resume_until = %s
                WHERE token_hash = %s
                """,
                (created_at, disconnected_at, disconnected_at, expired_at, token_hash),
            )
        conn.commit()


def _auth_log_row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "username_attempted": row[1],
        "user_id": str(row[2]) if row[2] is not None else None,
        "client_ip": str(row[3]) if row[3] is not None else None,
        "event_type": row[4],
        "success": row[5],
        "error_code": row[6],
        "created_at": row[7],
    }



def fetch_auth_logs_by_username(username: str, event_type: str | None = None) -> list[dict]:
    query = """
        SELECT id, username_attempted, user_id, client_ip,
               event_type, success, error_code, created_at
        FROM auth_logs
        WHERE username_attempted = %s
    """
    params = [username]

    if event_type is not None:
        query += " AND event_type = %s"
        params.append(event_type)

    query += " ORDER BY id ASC"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    return [_auth_log_row_to_dict(row) for row in rows]



def fetch_auth_logs_by_user_id(user_id: str, event_type: str | None = None) -> list[dict]:
    query = """
        SELECT id, username_attempted, user_id, client_ip,
               event_type, success, error_code, created_at
        FROM auth_logs
        WHERE user_id = %s
    """
    params = [user_id]

    if event_type is not None:
        query += " AND event_type = %s"
        params.append(event_type)

    query += " ORDER BY id ASC"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    return [_auth_log_row_to_dict(row) for row in rows]



def get_latest_auth_log_by_username(username: str, event_type: str | None = None) -> dict | None:
    logs = fetch_auth_logs_by_username(username, event_type)
    return logs[-1] if logs else None



def get_latest_auth_log_by_user_id(user_id: str, event_type: str | None = None) -> dict | None:
    logs = fetch_auth_logs_by_user_id(user_id, event_type)
    return logs[-1] if logs else None



def cleanup_auth_logs_for_username(username: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM auth_logs WHERE username_attempted = %s",
                (username,),
            )
        conn.commit()



def cleanup_auth_logs_for_user_id(user_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM auth_logs WHERE user_id = %s",
                (user_id,),
            )
        conn.commit()
