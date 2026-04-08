def create_request_history(
    conn,
    scope_key: str,
    request_id: str,
    message_type: str,
    request_hash: str,
    expires_at,
    response_code: int | None = None,
) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO request_history (
                scope_key,
                request_id,
                message_type,
                request_hash,
                response_code,
                expires_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, scope_key, request_id, message_type, request_hash, response_code, created_at, expires_at
            """,
            (scope_key, request_id, message_type, request_hash, response_code, expires_at),
        )
        row = cur.fetchone()

    return {
        "id": row[0],
        "scope_key": row[1],
        "request_id": row[2],
        "message_type": row[3],
        "request_hash": row[4],
        "response_code": row[5],
        "created_at": row[6],
        "expires_at": row[7],
    }



def get_request_history(conn, scope_key: str, request_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, scope_key, request_id, message_type, request_hash, response_code, created_at, expires_at
            FROM request_history
            WHERE scope_key = %s AND request_id = %s
            """,
            (scope_key, request_id),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row[0],
        "scope_key": row[1],
        "request_id": row[2],
        "message_type": row[3],
        "request_hash": row[4],
        "response_code": row[5],
        "created_at": row[6],
        "expires_at": row[7],
    }



def update_request_history_response_code(conn, scope_key: str, request_id: str, response_code: int) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE request_history
            SET response_code = %s
            WHERE scope_key = %s AND request_id = %s
            """,
            (response_code, scope_key, request_id),
        )
        return cur.rowcount > 0



def delete_request_history_record(conn, scope_key: str, request_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM request_history
            WHERE scope_key = %s AND request_id = %s
            """,
            (scope_key, request_id),
        )
        return cur.rowcount > 0
