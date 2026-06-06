import json
import uuid
from datetime import datetime, timezone


class MsgType:
    # Handshake
    HELLO          = "HELLO"
    HELLO_OK       = "HELLO_OK"
    BYE            = "BYE"

    # Utrzymanie połączenia
    PING           = "PING"
    PONG           = "PONG"

    # Autentykacja / sesja
    LOGIN_OK       = "LOGIN_OK"
    RESUME_SESSION = "RESUME_SESSION"
    RESUME_SESSION_OK = "RESUME_SESSION_OK"

    # Zadania
    CREATE_TASK    = "CREATE_TASK"
    TASK_CREATED   = "TASK_CREATED"
    UPDATE_TASK    = "UPDATE_TASK"
    TASK_UPDATED   = "TASK_UPDATED"
    DELETE_TASK    = "DELETE_TASK"
    TASK_DELETED   = "TASK_DELETED"

    # Błędy
    ERROR          = "ERROR"

    # Typy, które nie wymagają wstrzykiwania tokenu sesji
    NO_AUTH_REQUIRED = {PING, HELLO, BYE}


# Budowanie ramki protokołu
def build_frame(msg_type: str, payload: dict, session_token: str | None = None) -> bytes:
    if session_token and msg_type not in MsgType.NO_AUTH_REQUIRED:
        payload.setdefault("session_token", session_token)

    message = {
        "type":       msg_type,
        "version":    "1.0",
        "request_id": str(uuid.uuid4()),
        "timestamp":  datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload":    payload,
    }
    json_bytes = json.dumps(message, ensure_ascii=False).encode("utf-8")
    size_header = len(json_bytes).to_bytes(4, byteorder="big")
    return size_header + json_bytes


# Parsowanie ramki
def parse_frame(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8"))

# Zwraca request_id z gotowej ramki
def extract_request_id(frame_bytes: bytes) -> str:
    return parse_frame(frame_bytes[4:])["request_id"]