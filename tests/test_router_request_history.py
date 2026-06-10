import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from server.db.db import get_connection
from server.protocol.router import ConnectionState, dispatch
from server.security.security_utils import hash_token
from tests.tests_utils import cleanup_request_history


IP = "127.0.0.1"


def _make_msg(msg_type: str, request_id: str, payload: dict | None = None) -> dict:
    return {
        "type": msg_type,
        "version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "request_id": request_id,
        "payload": payload or {},
    }


def _make_msg_with_timestamp(
    msg_type: str,
    request_id: str,
    timestamp: str,
    payload: dict | None = None,
) -> dict:
    message = _make_msg(msg_type, request_id, payload)
    message["timestamp"] = timestamp
    return message


def _get_request_history(scope_key: str, request_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT scope_key, request_id, message_type, response_code
                FROM request_history
                WHERE scope_key = %s AND request_id = %s
                """,
                (scope_key, request_id),
            )
            row = cur.fetchone()

    if row is None:
        return None

    return {
        "scope_key": row[0],
        "request_id": row[1],
        "message_type": row[2],
        "response_code": row[3],
    }


def test_router_request_history_uses_hashed_session_scope_and_detects_duplicate():
    session_token = f"plain-session-token-{uuid.uuid4().hex}"
    request_id = f"req-{uuid.uuid4().hex[:12]}"
    expected_scope_key = f"session:{hash_token(session_token)}"
    msg = _make_msg("CREATE_TASK", request_id, {"title": "Safe scope"})

    cleanup_request_history(expected_scope_key)

    try:
        with patch("server.protocol.router.check_rate_limit", return_value={"ok": True}):
            with patch(
                "server.protocol.router.create_task",
                return_value={"ok": True, "task": {"id": "task-1", "title": "Safe scope"}},
            ) as mock_create_task:
                response_type, payload, new_state = dispatch(
                    msg,
                    ConnectionState.ACTIVE,
                    IP,
                    session_token,
                )
                duplicate_type, duplicate_payload, duplicate_state = dispatch(
                    msg,
                    ConnectionState.ACTIVE,
                    IP,
                    session_token,
                )

        history = _get_request_history(expected_scope_key, request_id)

        assert response_type == "TASK_CREATED"
        assert payload["task"]["id"] == "task-1"
        assert new_state is None
        assert history is not None
        assert history["scope_key"] == expected_scope_key
        assert history["scope_key"].startswith("session:")
        assert session_token not in history["scope_key"]
        assert history["response_code"] == 0

        assert duplicate_type == "ERROR"
        assert duplicate_payload["error_code"] == 301
        assert duplicate_state is None
        mock_create_task.assert_called_once()
    finally:
        cleanup_request_history(expected_scope_key)


def test_router_rejects_old_timestamp_before_request_history_write():
    session_token = f"plain-session-token-{uuid.uuid4().hex}"
    request_id = f"req-{uuid.uuid4().hex[:12]}"
    expected_scope_key = f"session:{hash_token(session_token)}"
    old_timestamp = (
        datetime.now(timezone.utc) - timedelta(minutes=2)
    ).isoformat().replace("+00:00", "Z")
    msg = _make_msg_with_timestamp(
        "CREATE_TASK",
        request_id,
        old_timestamp,
        {"title": "Too old"},
    )

    cleanup_request_history(expected_scope_key)

    try:
        with patch("server.protocol.router.check_rate_limit") as mock_rate_limit:
            with patch("server.protocol.router.create_task") as mock_create_task:
                response_type, payload, new_state = dispatch(
                    msg,
                    ConnectionState.ACTIVE,
                    IP,
                    session_token,
                )

        history = _get_request_history(expected_scope_key, request_id)

        assert response_type == "ERROR"
        assert payload["error_code"] == 100
        assert "Timestamp outside allowed window" in payload["message"]
        assert new_state is None
        assert history is None
        mock_rate_limit.assert_not_called()
        mock_create_task.assert_not_called()
    finally:
        cleanup_request_history(expected_scope_key)


def test_router_rejects_rate_limited_request_before_request_history_write():
    session_token = f"plain-session-token-{uuid.uuid4().hex}"
    allowed_request_id = f"req-{uuid.uuid4().hex[:12]}"
    blocked_request_id = f"req-{uuid.uuid4().hex[:12]}"
    expected_scope_key = f"session:{hash_token(session_token)}"
    allowed_msg = _make_msg("CREATE_TASK", allowed_request_id, {"title": "Allowed"})
    blocked_msg = _make_msg("CREATE_TASK", blocked_request_id, {"title": "Blocked"})

    cleanup_request_history(expected_scope_key)

    try:
        with patch(
            "server.protocol.router.check_rate_limit",
            side_effect=[
                {"ok": True},
                {"ok": False, "error_code": 400, "message": "Rate limit exceeded"},
            ],
        ) as mock_rate_limit:
            with patch(
                "server.protocol.router.create_task",
                return_value={"ok": True, "task": {"id": "task-1", "title": "Allowed"}},
            ) as mock_create_task:
                allowed_type, allowed_payload, allowed_state = dispatch(
                    allowed_msg,
                    ConnectionState.ACTIVE,
                    IP,
                    session_token,
                )
                blocked_type, blocked_payload, blocked_state = dispatch(
                    blocked_msg,
                    ConnectionState.ACTIVE,
                    IP,
                    session_token,
                )

        allowed_history = _get_request_history(expected_scope_key, allowed_request_id)
        blocked_history = _get_request_history(expected_scope_key, blocked_request_id)

        assert allowed_type == "TASK_CREATED"
        assert allowed_payload["task"]["id"] == "task-1"
        assert allowed_state is None
        assert allowed_history is not None

        assert blocked_type == "ERROR"
        assert blocked_payload["error_code"] == 400
        assert "Rate limit exceeded" in blocked_payload["message"]
        assert blocked_state is None
        assert blocked_history is None

        assert mock_rate_limit.call_count == 2
        mock_rate_limit.assert_any_call(expected_scope_key)
        mock_create_task.assert_called_once()
    finally:
        cleanup_request_history(expected_scope_key)
