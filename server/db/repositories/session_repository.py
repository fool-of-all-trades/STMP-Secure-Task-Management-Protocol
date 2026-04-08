def create_session(conn, user_id: str, token_hash: str, client_ip: str | None, expires_at) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sessions (user_id, token_hash, client_ip, expires_at, resume_until)
            VALUES (%s, %s, %s, %s, NULL)
            RETURNING id, user_id, expires_at
            """,
            (user_id, token_hash, client_ip, expires_at),
        )
        row = cur.fetchone()

    return {
        "id": row[0],
        "user_id": row[1],
        "expires_at": row[2],
    }


def get_session_by_token_hash(conn, token_hash: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, user_id, client_ip, created_at, last_seen_at,
                   expires_at, disconnected_at, resume_until, revoked_at
            FROM sessions
            WHERE token_hash = %s
            """,
            (token_hash,),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "user_id": row[1],
        "client_ip": row[2],
        "created_at": row[3],
        "last_seen_at": row[4],
        "expires_at": row[5],
        "disconnected_at": row[6],
        "resume_until": row[7],
        "revoked_at": row[8],
    }


def touch_session(conn, session_id: str, now) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sessions
            SET last_seen_at = %s
            WHERE id = %s
            """,
            (now, session_id),
        )


def revoke_session(conn, token_hash: str, revoked_at) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sessions
            SET revoked_at = %s
            WHERE token_hash = %s
            RETURNING id, user_id
            """,
            (revoked_at, token_hash),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "user_id": row[1],
    }


def mark_session_disconnected(conn, session_id: str, disconnected_at, resume_until) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sessions
            SET disconnected_at = %s,
                resume_until = %s
            WHERE id = %s
            """,
            (disconnected_at, resume_until, session_id),
        )


def resume_session_record(conn, session_id: str, client_ip: str | None, now) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE sessions
            SET disconnected_at = NULL,
                resume_until = NULL,
                last_seen_at = %s,
                client_ip = %s
            WHERE id = %s
            """,
            (now, client_ip, session_id),
        )