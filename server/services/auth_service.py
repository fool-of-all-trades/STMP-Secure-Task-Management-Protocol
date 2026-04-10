from datetime import datetime, timedelta, timezone

from server.db.db import get_connection
from server.db.repositories.auth_log_repository import log_auth_event
from server.db.repositories.session_repository import create_session, revoke_session
from server.db.repositories.user_repository import (
    create_user,
    get_user_by_username,
    reset_failed_logins,
    update_failed_login,
)
from server.security.security_config import (
    LOCK_TIME_MINUTES,
    MAX_FAILED_LOGINS,
    SESSION_LIFETIME_MINUTES,
)
from server.security.security_utils import (
    generate_session_token,
    hash_password,
    hash_token,
    verify_password,
)


def register_user(username: str, password: str, client_ip: str | None = None) -> dict:
    username = username.strip() if username else ""

    if not username or len(username) > 64:
        return {"ok": False, "error_code": 105, "message": "Invalid username length"}

    if not password or len(password) > 128:
        return {"ok": False, "error_code": 105, "message": "Invalid password length"}

    password_hash = hash_password(password)

    with get_connection() as conn:
        try:
            existing_user = get_user_by_username(conn, username)

            if existing_user:
                log_auth_event(conn, username, None, client_ip, "REGISTER", False, 204)
                conn.commit()
                return {"ok": False, "error_code": 204, "message": "User already exists"}

            created_user = create_user(conn, username, password_hash)

            log_auth_event(conn, username, created_user["id"], client_ip, "REGISTER", True, None)
            conn.commit()

            return {
                "ok": True,
                "user_id": str(created_user["id"]),
                "message": "User registered successfully",
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}


def login_user(username: str, password: str, client_ip: str | None = None) -> dict:
    username = username.strip() if username else ""
    now = datetime.now(timezone.utc)

    with get_connection() as conn:
        try:
            user = get_user_by_username(conn, username)

            if not user:
                log_auth_event(conn, username, None, client_ip, "LOGIN", False, 200)
                conn.commit()
                return {"ok": False, "error_code": 200, "message": "Invalid username or password"}

            if user["locked_until"] is not None and user["locked_until"] > now:
                log_auth_event(conn, username, user["id"], client_ip, "LOGIN", False, 203)
                conn.commit()
                return {"ok": False, "error_code": 203, "message": "Account temporarily locked"}

            if not verify_password(password, user["password_hash"]):
                new_failed_count = user["failed_login_count"] + 1
                new_locked_until = None

                if new_failed_count >= MAX_FAILED_LOGINS:
                    new_locked_until = now + timedelta(minutes=LOCK_TIME_MINUTES)
                    new_failed_count = 0

                update_failed_login(conn, user["id"], new_failed_count, new_locked_until)
                log_auth_event(conn, username, user["id"], client_ip, "LOGIN", False, 200)
                conn.commit()

                return {"ok": False, "error_code": 200, "message": "Invalid username or password"}

            reset_failed_logins(conn, user["id"])

            raw_token = generate_session_token()
            token_hash = hash_token(raw_token)
            expires_at = now + timedelta(minutes=SESSION_LIFETIME_MINUTES)

            session = create_session(conn, user["id"], token_hash, client_ip, expires_at)

            log_auth_event(conn, username, user["id"], client_ip, "LOGIN", True, None)
            conn.commit()

            return {
                "ok": True,
                "user_id": str(user["id"]),
                "session_id": str(session["id"]),
                "session_token": raw_token,
                "expires_at": session["expires_at"].isoformat(),
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}


def logout_user(session_token: str) -> dict:
    if not session_token:
        return {"ok": False, "error_code": 202, "message": "Session expired"}

    now = datetime.now(timezone.utc)
    token_hash = hash_token(session_token)

    with get_connection() as conn:
        try:
            revoked_session = revoke_session(conn, token_hash, now)

            if not revoked_session:
                conn.commit()
                return {"ok": False, "error_code": 202, "message": "Session expired"}

            log_auth_event(conn, None, revoked_session["user_id"], None, "LOGOUT", True, None)
            conn.commit()

            return {
                "ok": True,
                "session_id": str(revoked_session["id"]),
                "user_id": str(revoked_session["user_id"]),
                "message": "Logged out",
            }

        except Exception:
            conn.rollback()
            return {"ok": False, "error_code": 500, "message": "Internal error"}