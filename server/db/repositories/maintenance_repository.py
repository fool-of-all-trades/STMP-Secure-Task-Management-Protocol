def delete_expired_sessions(conn, now) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM sessions
            WHERE expires_at <= %s
            RETURNING id
            """,
            (now,),
        )
        deleted_rows = cur.fetchall()

    return len(deleted_rows)



def delete_expired_request_history(conn, now) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM request_history
            WHERE expires_at <= %s
            RETURNING id
            """,
            (now,),
        )
        deleted_rows = cur.fetchall()

    return len(deleted_rows)
