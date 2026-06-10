from enum import Enum

from server.services.auth_service import login_user, logout_user, register_user
from server.services.session_service import (
    mark_session_as_disconnected,
    resume_session,
    validate_session,
)
from server.services.task_service import (
    create_task,
    delete_task,
    list_tasks,
    update_task,
)
from server.services.rate_limit_service import check_rate_limit
from server.services.request_guard_service import (
    register_request,
    validate_message_timestamp,
    set_request_response_code,
)
from server.security.security_utils import hash_token


# stany polaczenia
class ConnectionState(Enum):
    CONNECTED = "CONNECTED"          # TCP + TLS, przed HELLO
    AUTHENTICATED = "AUTHENTICATED"  # po HELLO, przed LOGIN
    ACTIVE = "ACTIVE"                # zalogowany i aktywny
    DISCONNECTED = "DISCONNECTED"    # rozlaczony


# wiadomosci dozwolone w kazdym stanie
STATE_ALLOWED = {
    ConnectionState.CONNECTED:     {"HELLO"},
    ConnectionState.AUTHENTICATED: {"LOGIN", "REGISTER", "RESUME_SESSION"},
    ConnectionState.ACTIVE:        {"CREATE_TASK", "UPDATE_TASK", "DELETE_TASK",
                                    "GET_TASK", "PING", "BYE", "RESUME_SESSION",
                                    "REFRESH_TOKEN"},
}


def _error(error_code: int, message: str) -> tuple[str, dict, None]:
    return "ERROR", {"error_code": error_code, "message": message}, None


def _ok(response_type: str, payload: dict, new_state: ConnectionState | None = None):
    return response_type, payload, new_state


def _build_scope_key(session_token: str | None, ip: str) -> str:
    if session_token:
        return f"session:{hash_token(session_token)}"
    return f"ip:{ip}"

# handlery ====================================================================

def handle_hello(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    if state != ConnectionState.CONNECTED:
        return _error(101, "HELLO already sent")
    return _ok("HELLO_OK", {"message": "Welcome to STMP/1.0"}, ConnectionState.AUTHENTICATED)


def handle_register(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    payload = message["payload"]
    username = payload.get("username", "")
    password = payload.get("password", "")

    if not username or not password:
        return _error(103, "Missing username or password")

    result = register_user(username, password, ip)

    if not result["ok"]:
        return _error(result["error_code"], result["message"])

    return _ok("REGISTER_OK", {"user_id": result["user_id"], "message": "User registered successfully"})


def handle_login(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    payload = message["payload"]
    username = payload.get("username", "")
    password = payload.get("password", "")

    if not username or not password:
        return _error(103, "Missing username or password")

    result = login_user(username, password, ip)

    if not result["ok"]:
        return _error(result["error_code"], result["message"])

    return _ok(
        "LOGIN_OK",
        {
            "session_token": result["session_token"],
            "user_id": result["user_id"],
            "expires_at": result["expires_at"],
        },
        ConnectionState.ACTIVE,
    )


def handle_resume_session(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    token = message["payload"].get("session_token", "")
    if not token:
        return _error(103, "Missing session_token")

    result = resume_session(token, ip)
    if not result["ok"]:
        return _error(result["error_code"], result["message"])

    return _ok("RESUME_SESSION_OK", {"message": "Session resumed"}, ConnectionState.ACTIVE)


def handle_ping(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    return _ok("PONG", {})


def handle_bye(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    if session_token:
        logout_user(session_token)
    return _ok("BYE", {"message": "Goodbye"}, ConnectionState.DISCONNECTED)


def handle_create_task(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    payload = message["payload"]
    title = payload.get("title", "")
    description = payload.get("description", "")
    status = payload.get("status", "todo")

    if not title:
        return _error(103, "Missing task title")

    result = create_task(session_token, title, description, status, ip)
    if not result["ok"]:
        return _error(result["error_code"], result["message"])

    return _ok("TASK_CREATED", {"task": result["task"]})


def handle_update_task(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    payload = message["payload"]
    task_id = payload.get("task_id", "")
    title = payload.get("title", "")
    description = payload.get("description", "")
    status = payload.get("status", "todo")

    if not task_id:
        return _error(103, "Missing task_id")

    if not title:
        return _error(103, "Missing task title")

    result = update_task(session_token, task_id, title, description, status, ip)
    if not result["ok"]:
        return _error(result["error_code"], result["message"])

    return _ok("TASK_UPDATED", {"task": result["task"]})


def handle_delete_task(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    task_id = message["payload"].get("task_id", "")
    if not task_id:
        return _error(103, "Missing task_id")

    result = delete_task(session_token, task_id, ip)
    if not result["ok"]:
        return _error(result["error_code"], result["message"])

    return _ok("TASK_DELETED", {"task_id": result["task_id"]})


def handle_get_task(message: dict, state: ConnectionState, ip: str, session_token: str | None):
    # GET_TASK bez task_id zwraca liste wszystkich
    task_id = message["payload"].get("task_id")

    if task_id:
        # pojedyncze zadanie
        result = list_tasks(session_token, ip)
        if not result["ok"]:
            return _error(result["error_code"], result["message"])
        tasks = [t for t in result["tasks"] if t["id"] == task_id]
        if not tasks:
            return _error(300, "Task not found")
        return _ok("TASK_DATA", {"task": tasks[0]})
    else:
        result = list_tasks(session_token, ip)
        if not result["ok"]:
            return _error(result["error_code"], result["message"])
        return _ok("TASK_LIST", {"tasks": result["tasks"]})


# router ======================================================================

HANDLERS = {
    "HELLO":          handle_hello,
    "REGISTER":       handle_register,
    "LOGIN":          handle_login,
    "RESUME_SESSION": handle_resume_session,
    "PING":           handle_ping,
    "BYE":            handle_bye,
    "CREATE_TASK":    handle_create_task,
    "UPDATE_TASK":    handle_update_task,
    "DELETE_TASK":    handle_delete_task,
    "GET_TASK":       handle_get_task,
}


def dispatch(
    message: dict,
    state: ConnectionState,
    ip: str,
    session_token: str | None,
) -> tuple[str, dict, ConnectionState | None]:
    """
    Glowny router z obsluga duplikatow.
    Zwraca: (response_type, payload, new_state)
    """
    msg_type = message["type"]
    request_id = message["request_id"]
    scope_key = _build_scope_key(session_token, ip)
 
    # Sprawdz stan
    allowed = STATE_ALLOWED.get(state, set())
    if msg_type not in allowed:
        if state == ConnectionState.CONNECTED:
            return _error(101, f"Expected HELLO, got {msg_type}")
        elif state == ConnectionState.AUTHENTICATED:
            return _error(101, f"Expected LOGIN, REGISTER or RESUME_SESSION, got {msg_type}")
        else:
            return _error(201, "Session required")
 
    ts_result = validate_message_timestamp(message["timestamp"])
    if not ts_result["ok"]:
        return _error(ts_result["error_code"], ts_result["message"])

    skip_dedup = msg_type in {"PING", "HELLO"}
    skip_rate_limit = msg_type in {"PING", "HELLO"}

    if not skip_rate_limit:
        rl_result = check_rate_limit(scope_key)
        if not rl_result["ok"]:
            return _error(rl_result["error_code"], rl_result["message"])
 
    # Obsluga duplikatow
    if not skip_dedup:
        dedup_result = register_request(
            scope_key=scope_key,
            request_id=request_id,
            message_type=msg_type,
            payload=message["payload"],
        )
        if not dedup_result["ok"]:
            if dedup_result["error_code"] == 301:
                return _error(301, "Duplicate request")
            return _error(dedup_result["error_code"], dedup_result["message"])
 
    handler = HANDLERS.get(msg_type)
    if not handler:
        return _error(101, f"Unknown message type: {msg_type}")
 
    response_type, payload, new_state = handler(message, state, ip, session_token)
 
    # Zapisz kod odpowiedzi w historii
    if not skip_dedup:
        response_code = 0 if response_type != "ERROR" else payload.get("error_code", 500)
        set_request_response_code(scope_key, request_id, response_code)
 
    return response_type, payload, new_state
