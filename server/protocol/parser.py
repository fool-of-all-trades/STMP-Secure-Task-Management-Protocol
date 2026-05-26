import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("parser")

SUPPORTED_VERSION = "1.0"
MAX_MESSAGE_SIZE = 64 * 1024  # 64 KB
FRAME_TIMEOUT = 3  # sekundy – timeout na odebranie pełnej ramki

# Wymagane pola w każdej wiadomości
REQUIRED_FIELDS = {"type", "version", "request_id", "timestamp", "payload"}

# Typy wiadomości które serwer obsługuje
ALLOWED_TYPES = {
    "HELLO",
    "LOGIN",
    "REGISTER",
    "RESUME_SESSION",
    "CREATE_TASK",
    "UPDATE_TASK",
    "DELETE_TASK",
    "GET_TASK",
    "PING",
    "BYE",
    "REFRESH_TOKEN",
}


def _build_error(error_code: int, message: str) -> dict:
    """Buduje odpowiedź błędu dla handlera."""
    return {
        "ok": False,
        "error_code": error_code,
        "message": message,
    }


def _validate_field_type(field_name: str, value, expected_type: type) -> dict | None:
    """
    Waliduje typ pola.
    Zwraca błąd jeśli typ się nie zgadza, None jeśli OK.
    """
    if not isinstance(value, expected_type):
        return _build_error(
            104,
            f"Invalid field type: {field_name} expected {expected_type.__name__}, "
            f"got {type(value).__name__}",
        )
    return None


def _validate_message_structure(message: dict) -> dict | None:
    """
    Waliduje strukturę wiadomości.
    Zwraca błąd lub None jeśli OK.
    """


    missing = REQUIRED_FIELDS - set(message.keys())
    if missing:
        return _build_error(
            103,
            f"Missing required fields: {', '.join(sorted(missing))}",
        )

    # Walidacja typów pól 

    error = _validate_field_type("type", message["type"], str)
    if error:
        return error

    error = _validate_field_type("version", message["version"], str)
    if error:
        return error

    error = _validate_field_type("request_id", message["request_id"], str)
    if error:
        return error

    error = _validate_field_type("timestamp", message["timestamp"], str)
    if error:
        return error

    error = _validate_field_type("payload", message["payload"], dict)
    if error:
        return error

    # Walidacja wersji protokołu

    if message["version"] != SUPPORTED_VERSION:
        return _build_error(
            102,
            f"Unsupported protocol version: {message['version']} "
            f"(expected {SUPPORTED_VERSION})",
        )

    # Walidacja typu wiadomości

    if message["type"] not in ALLOWED_TYPES:
        return _build_error(
            101,
            f"Unknown message type: {message['type']}",
        )

    # request_id nie powinno być puste 

    if not message["request_id"].strip():
        return _build_error(
            103,
            "request_id cannot be empty",
        )

    # timestamp powinien być w formacie ISO 8601

    try:
        datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00"))
    except ValueError:
        return _build_error(
            100,
            "Invalid timestamp format (expected ISO 8601, e.g., 2026-03-10T18:30:00Z)",
        )

    return None


# Czytanie ramki

async def _read_exact(
    reader: asyncio.StreamReader,
    n: int,
    timeout: float = FRAME_TIMEOUT,
) -> bytes | None:
    """
    Czyta dokładnie n bajtów z reader'a z timeoutem.
    Zwraca None jeśli timeout lub koniec strumienia.
    """
    try:
        data = await asyncio.wait_for(reader.readexactly(n), timeout=timeout)
        return data
    except asyncio.TimeoutError:
        logger.warning("Frame timeout – client didn't send data within %s seconds", timeout)
        return None
    except asyncio.IncompleteReadError:
        logger.warning("Incomplete frame – client disconnected")
        return None


async def parse_message(reader: asyncio.StreamReader) -> dict:
    """
    Parsuje wiadomość z klienta.
    """

    # Czytaj nagłówek (4 bajty – rozmiar) i payload (JSON)

    size_bytes = await _read_exact(reader, 4, timeout=FRAME_TIMEOUT)
    if size_bytes is None:
        return _build_error(100, "Could not read message size (frame timeout)")

    message_size = int.from_bytes(size_bytes, byteorder="big")

    # Sprawdź rozmiar

    if message_size <= 0:
        return _build_error(100, "Invalid message size (must be > 0)")

    if message_size > MAX_MESSAGE_SIZE:
        return _build_error(
            105,
            f"Message too large: {message_size} bytes (max {MAX_MESSAGE_SIZE})",
        )

    # Czytaj payload

    json_bytes = await _read_exact(reader, message_size, timeout=FRAME_TIMEOUT)
    if json_bytes is None:
        return _build_error(100, "Could not read message payload (frame timeout)")

    # Parsuj JSON i waliduj strukturę
    try:
        message_dict = json.loads(json_bytes.decode("utf-8"))
    except json.JSONDecodeError as e:
        return _build_error(100, f"Invalid JSON: {str(e)}")
    except UnicodeDecodeError:
        return _build_error(100, "Invalid UTF-8 encoding")

    if not isinstance(message_dict, dict):
        return _build_error(100, "Message must be a JSON object, not array or primitive")

    validation_error = _validate_message_structure(message_dict)
    if validation_error:
        return validation_error

    logger.debug("Parsed message: type=%s, request_id=%s", message_dict["type"], message_dict["request_id"])

    return {
        "ok": True,
        "message": message_dict,
    }


# Budowanie odpowiedzi

def build_response(message_type: str, payload: dict, request_id: str = "") -> bytes:
    """
    Buduje length-prefixed JSON odpowiedź.

    Zwraca: [4 bajty rozmiar] [JSON]
    """
    response = {
        "type": message_type,
        "version": SUPPORTED_VERSION,
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": payload,
    }
    json_bytes = json.dumps(response, ensure_ascii=False).encode("utf-8")
    size_bytes = len(json_bytes).to_bytes(4, byteorder="big")
    return size_bytes + json_bytes