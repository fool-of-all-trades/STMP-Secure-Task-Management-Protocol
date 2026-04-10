import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from server.db.db import get_connection
from server.db.repositories.request_history_repository import (
    create_request_history,
    delete_request_history_record,
    get_request_history,
    update_request_history_response_code,
)
from server.security.security_config import (
    REQUEST_HISTORY_TTL_SECONDS,
    TIMESTAMP_TOLERANCE_SECONDS,
)



def _canonicalize_payload(payload: Any) -> str:
    if payload is None:
        return "null"

    if isinstance(payload, (dict, list, tuple, bool, int, float)):
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    return str(payload)



def build_request_hash(message_type: str, payload: Any) -> str:
    canonical_message = json.dumps(
        {
            "message_type": message_type,
            "payload": _canonicalize_payload(payload),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical_message.encode("utf-8")).hexdigest()



def validate_message_timestamp(
    timestamp_value: str,
    now: datetime | None = None,
    tolerance_seconds: int = TIMESTAMP_TOLERANCE_SECONDS,
) -> dict:
    if not isinstance(timestamp_value, str) or not timestamp_value.strip():
        return {"ok": False, "error_code": 100, "message": "Invalid timestamp format"}

    try:
        parsed = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
    except ValueError:
        return {"ok": False, "error_code": 100, "message": "Invalid timestamp format"}

    if parsed.tzinfo is None:
        return {"ok": False, "error_code": 100, "message": "Timestamp must include timezone"}

    current_time = now or datetime.now(timezone.utc)
    parsed_utc = parsed.astimezone(timezone.utc)
    skew_seconds = abs((current_time - parsed_utc).total_seconds())

    if skew_seconds > tolerance_seconds:
        return {"ok": False, "error_code": 100, "message": "Timestamp outside allowed window"}

    return {
        "ok": True,
        "timestamp": parsed_utc.isoformat(),
        "skew_seconds": skew_seconds,
    }



def register_request(
    scope_key: str,
    request_id: str,
    message_type: str,
    payload: Any,
    response_code: int | None = None,
    now: datetime | None = None,
    ttl_seconds: int = REQUEST_HISTORY_TTL_SECONDS,
) -> dict:
    scope_key = scope_key.strip() if isinstance(scope_key, str) else ""
    request_id = request_id.strip() if isinstance(request_id, str) else ""
    message_type = message_type.strip() if isinstance(message_type, str) else ""

    if not scope_key or not request_id or not message_type:
        return {"ok": False, "error_code": 103, "message": "Missing required request metadata"}

    current_time = now or datetime.now(timezone.utc)
    request_hash = build_request_hash(message_type, payload)

    with get_connection() as conn:
        try:
            existing = get_request_history(conn, scope_key, request_id)

            if existing and existing["expires_at"] > current_time:
                same_payload = existing["request_hash"] == request_hash
                conn.commit()
                return {
                    "ok": False,
                    "error_code": 301,
                    "message": "Duplicate request",
                    "same_payload": same_payload,
                    "response_code": existing["response_code"],
                    "request_hash": request_hash,
                }

            if existing and existing["expires_at"] <= current_time:
                delete_request_history_record(conn, scope_key, request_id)

            expires_at = current_time + timedelta(seconds=ttl_seconds)
            created = create_request_history(
                conn,
                scope_key=scope_key,
                request_id=request_id,
                message_type=message_type,
                request_hash=request_hash,
                response_code=response_code,
                expires_at=expires_at,
            )
            conn.commit()

            return {
                "ok": True,
                "request_id": created["request_id"],
                "scope_key": created["scope_key"],
                "request_hash": created["request_hash"],
                "expires_at": created["expires_at"].isoformat(),
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}



def set_request_response_code(scope_key: str, request_id: str, response_code: int) -> dict:
    with get_connection() as conn:
        try:
            updated = update_request_history_response_code(conn, scope_key, request_id, response_code)
            conn.commit()

            if not updated:
                return {"ok": False, "error_code": 300, "message": "Request history not found"}

            return {
                "ok": True,
                "scope_key": scope_key,
                "request_id": request_id,
                "response_code": response_code,
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}
