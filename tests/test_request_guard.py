import uuid
from datetime import datetime, timedelta, timezone

from server.db.db import get_connection
from server.services.request_guard_service import (
    register_request,
    set_request_response_code,
    validate_message_timestamp,
)
from tests.tests_utils import cleanup_request_history, count_request_history_records



def _get_request_response_code(scope_key: str, request_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT response_code
                FROM request_history
                WHERE scope_key = %s AND request_id = %s
                """,
                (scope_key, request_id),
            )
            row = cur.fetchone()
    return None if row is None else row[0]



def test_validate_message_timestamp_accepts_value_within_tolerance():
    now = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)
    timestamp_value = (now - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")

    result = validate_message_timestamp(timestamp_value, now=now)

    assert result["ok"] is True
    assert result["skew_seconds"] == 10



def test_validate_message_timestamp_rejects_old_value():
    now = datetime(2026, 4, 2, 15, 0, 0, tzinfo=timezone.utc)
    timestamp_value = (now - timedelta(seconds=61)).isoformat().replace("+00:00", "Z")

    result = validate_message_timestamp(timestamp_value, now=now, tolerance_seconds=30)

    assert result["ok"] is False
    assert result["error_code"] == 100



def test_validate_message_timestamp_rejects_invalid_format():
    result = validate_message_timestamp("not-a-timestamp")

    assert result["ok"] is False
    assert result["error_code"] == 100



def test_register_request_stores_first_request_and_detects_duplicate_same_payload():
    scope_key = f"request-guard-{uuid.uuid4().hex[:8]}"
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    payload = {"title": "Test task", "status": "todo"}

    cleanup_request_history(scope_key)

    first_result = register_request(scope_key, request_id, "CREATE_TASK", payload)
    duplicate_result = register_request(scope_key, request_id, "CREATE_TASK", payload)

    assert first_result["ok"] is True
    assert count_request_history_records(scope_key, request_id) == 1

    assert duplicate_result["ok"] is False
    assert duplicate_result["error_code"] == 301
    assert duplicate_result["same_payload"] is True

    cleanup_request_history(scope_key)



def test_register_request_detects_duplicate_request_id_with_different_payload():
    scope_key = f"request-guard-{uuid.uuid4().hex[:8]}"
    request_id = f"req-{uuid.uuid4().hex[:8]}"

    cleanup_request_history(scope_key)

    first_result = register_request(scope_key, request_id, "UPDATE_TASK", {"title": "A"})
    duplicate_result = register_request(scope_key, request_id, "UPDATE_TASK", {"title": "B"})

    assert first_result["ok"] is True
    assert duplicate_result["ok"] is False
    assert duplicate_result["error_code"] == 301
    assert duplicate_result["same_payload"] is False

    cleanup_request_history(scope_key)



def test_set_request_response_code_updates_existing_record():
    scope_key = f"request-guard-{uuid.uuid4().hex[:8]}"
    request_id = f"req-{uuid.uuid4().hex[:8]}"

    cleanup_request_history(scope_key)

    create_result = register_request(scope_key, request_id, "DELETE_TASK", {"task_id": "123"})
    assert create_result["ok"] is True

    update_result = set_request_response_code(scope_key, request_id, 301)

    assert update_result["ok"] is True
    assert _get_request_response_code(scope_key, request_id) == 301

    cleanup_request_history(scope_key)
