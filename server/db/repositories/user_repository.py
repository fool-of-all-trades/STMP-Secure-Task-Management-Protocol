def get_user_by_username(conn, username: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, username, password_hash, failed_login_count, locked_until
            FROM users
            WHERE username = %s
            """,
            (username,),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "username": row[1],
        "password_hash": row[2],
        "failed_login_count": row[3],
        "locked_until": row[4],
    }


def create_user(conn, username: str, password_hash: str) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (username, password_hash)
            VALUES (%s, %s)
            RETURNING id, username, created_at
            """,
            (username, password_hash),
        )
        row = cur.fetchone()

    return {
        "id": row[0],
        "username": row[1],
        "created_at": row[2],
    }


def update_failed_login(conn, user_id: str, failed_login_count: int, locked_until) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE users
            SET failed_login_count = %s,
                locked_until = %s
            WHERE id = %s
            """,
            (failed_login_count, locked_until, user_id),
        )


def reset_failed_logins(conn, user_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE users
            SET failed_login_count = 0,
                locked_until = NULL
            WHERE id = %s
            """,
            (user_id,),
        )