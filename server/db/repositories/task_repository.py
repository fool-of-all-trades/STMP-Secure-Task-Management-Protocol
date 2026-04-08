def _row_to_task(row) -> dict:
    return {
        "id": row[0],
        "user_id": row[1],
        "title": row[2],
        "description": row[3],
        "status": row[4],
        "created_at": row[5],
        "updated_at": row[6],
    }


def create_task(conn, user_id: str, title: str, description: str, status: str = "todo") -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tasks (user_id, title, description, status)
            VALUES (%s, %s, %s, %s)
            RETURNING id, user_id, title, description, status, created_at, updated_at
            """,
            (user_id, title, description, status),
        )
        row = cur.fetchone()

    return _row_to_task(row)


def get_tasks_for_user(conn, user_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, user_id, title, description, status, created_at, updated_at
            FROM tasks
            WHERE user_id = %s
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()

    return [_row_to_task(row) for row in rows]


def get_task_by_id(conn, task_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, user_id, title, description, status, created_at, updated_at
            FROM tasks
            WHERE id = %s
            """,
            (task_id,),
        )
        row = cur.fetchone()

    if not row:
        return None

    return _row_to_task(row)


def update_task(conn, task_id: str, title: str, description: str, status: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tasks
            SET title = %s,
                description = %s,
                status = %s
            WHERE id = %s
            RETURNING id, user_id, title, description, status, created_at, updated_at
            """,
            (title, description, status, task_id),
        )
        row = cur.fetchone()

    if not row:
        return None

    return _row_to_task(row)


def delete_task(conn, task_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM tasks
            WHERE id = %s
            RETURNING id
            """,
            (task_id,),
        )
        row = cur.fetchone()

    return row is not None


def user_owns_task(conn, user_id: str, task_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM tasks
            WHERE id = %s AND user_id = %s
            """,
            (task_id, user_id),
        )
        return cur.fetchone() is not None