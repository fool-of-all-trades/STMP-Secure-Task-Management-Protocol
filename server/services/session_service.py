from datetime import datetime, timedelta, timezone

from server.db.db import get_connection
from server.db.repositories.auth_log_repository import log_auth_event
from server.db.repositories.session_repository import (
    get_session_by_token_hash,
    mark_session_disconnected,
    resume_session_record,
    touch_session,
)
from server.security.security_config import SESSION_RESUME_MINUTES
from server.security.security_utils import hash_token


def _log_session_event(
    conn,
    session: dict | None,
    client_ip: str | None,
    event_type: str,
    success: bool,
    error_code: int | None = None,
) -> None:
    user_id = session["user_id"] if session is not None else None
    resolved_ip = client_ip

    if resolved_ip is None and session is not None and session.get("client_ip") is not None:
        resolved_ip = str(session["client_ip"])

    log_auth_event(conn, None, user_id, resolved_ip, event_type, success, error_code)


def validate_session(session_token: str, client_ip: str | None = None) -> dict:
    if not session_token:
        with get_connection() as conn:
            try:
                _log_session_event(conn, None, client_ip, "SESSION_VALIDATE", False, 201)
                conn.commit()
            except Exception:
                conn.rollback()
        return {"ok": False, "error_code": 201, "message": "Session required"}

    now = datetime.now(timezone.utc)
    token_hash = hash_token(session_token)

    with get_connection() as conn:
        try:
            session = get_session_by_token_hash(conn, token_hash)

            if not session:
                _log_session_event(conn, None, client_ip, "SESSION_VALIDATE", False, 201)
                conn.commit()
                return {"ok": False, "error_code": 201, "message": "Session required"}

            if session["revoked_at"] is not None or session["expires_at"] <= now:
                _log_session_event(conn, session, client_ip, "SESSION_VALIDATE", False, 202)
                conn.commit()
                return {"ok": False, "error_code": 202, "message": "Session expired"}

            # Tutaj będzie token powiązany z IP ale na razie dla testów zostawiamy to wyłączone
            #
            # if (
            #     client_ip is not None
            #     and session["client_ip"] is not None
            #     and str(session["client_ip"]) != client_ip
            # ):
            #     _log_session_event(conn, session, client_ip, "SESSION_VALIDATE", False, 202)
            #     conn.commit()
            #     return {"ok": False, "error_code": 202, "message": "Session expired"}

            touch_session(conn, session["id"], now)
            _log_session_event(conn, session, client_ip, "SESSION_VALIDATE", True, None)
            conn.commit()

            return {
                "ok": True,
                "session_id": str(session["id"]),
                "user_id": str(session["user_id"]),
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}


def mark_session_as_disconnected(session_token: str) -> dict:
    if not session_token:
        with get_connection() as conn:
            try:
                _log_session_event(conn, None, None, "SESSION_DISCONNECT", False, 202)
                conn.commit()
            except Exception:
                conn.rollback()
        return {"ok": False, "error_code": 202, "message": "Session expired"}

    now = datetime.now(timezone.utc)
    token_hash = hash_token(session_token)

    with get_connection() as conn:
        try:
            session = get_session_by_token_hash(conn, token_hash)

            if not session:
                _log_session_event(conn, None, None, "SESSION_DISCONNECT", False, 202)
                conn.commit()
                return {"ok": False, "error_code": 202, "message": "Session expired"}

            if session["revoked_at"] is not None or session["expires_at"] <= now:
                _log_session_event(conn, session, None, "SESSION_DISCONNECT", False, 202)
                conn.commit()
                return {"ok": False, "error_code": 202, "message": "Session expired"}

            resume_until = now + timedelta(minutes=SESSION_RESUME_MINUTES)

            mark_session_disconnected(conn, session["id"], now, resume_until)
            _log_session_event(conn, session, None, "SESSION_DISCONNECT", True, None)
            conn.commit()

            return {
                "ok": True,
                "session_id": str(session["id"]),
                "user_id": str(session["user_id"]),
                "resume_until": resume_until.isoformat(),
                "message": "Session marked as disconnected",
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}


def resume_session(session_token: str, client_ip: str | None = None) -> dict:
    if not session_token:
        with get_connection() as conn:
            try:
                _log_session_event(conn, None, client_ip, "SESSION_RESUME", False, 202)
                conn.commit()
            except Exception:
                conn.rollback()
        return {"ok": False, "error_code": 202, "message": "Session expired"}

    now = datetime.now(timezone.utc)
    token_hash = hash_token(session_token)

    with get_connection() as conn:
        try:
            session = get_session_by_token_hash(conn, token_hash)

            if not session:
                _log_session_event(conn, None, client_ip, "SESSION_RESUME", False, 202)
                conn.commit()
                return {"ok": False, "error_code": 202, "message": "Session expired"}

            if session["revoked_at"] is not None or session["expires_at"] <= now:
                _log_session_event(conn, session, client_ip, "SESSION_RESUME", False, 202)
                conn.commit()
                return {"ok": False, "error_code": 202, "message": "Session expired"}

            if session["resume_until"] is None or session["resume_until"] < now:
                _log_session_event(conn, session, client_ip, "SESSION_RESUME", False, 202)
                conn.commit()
                return {"ok": False, "error_code": 202, "message": "Session expired"}

            # I znowu powiązanie tokena z IP
            #
            # if (
            #     client_ip is not None
            #     and session["client_ip"] is not None
            #     and str(session["client_ip"]) != client_ip
            # ):
            #     _log_session_event(conn, session, client_ip, "SESSION_RESUME", False, 202)
            #     conn.commit()
            #     return {"ok": False, "error_code": 202, "message": "Session expired"}

            resume_session_record(conn, session["id"], client_ip, now)
            _log_session_event(conn, session, client_ip, "SESSION_RESUME", True, None)
            conn.commit()

            return {
                "ok": True,
                "session_id": str(session["id"]),
                "user_id": str(session["user_id"]),
                "message": "Session resumed",
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}
