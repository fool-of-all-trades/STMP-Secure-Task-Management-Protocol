import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("parser")

# konfiguracja
SUPPORTED_VERSION = "1.0"
MAX_MESSAGE_SIZE = 64 * 1024  # 64 KB
FRAME_TIMEOUT = 3  # sekundy

REQUIRED_FIELDS = {"type", "version", "request_id", "timestamp", "payload"}

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
    return {
        "ok": False,
        "error_code": error_code,
        "message": message,
    }


def _validate_field_type(field_name: str, value, expected_type: type) -> dict | None:
    if not isinstance(value, expected_type):
        return _build_error(
            104,
            f"Invalid field type: {field_name} expected {expected_type.__name__}, "
            f"got {type(value).__name__}",
        )
    return None


def _validate_message_structure(message: dict) -> dict | None:
    missing = REQUIRED_FIELDS - set(message.keys())
    if missing:
        return _build_error(103, f"Missing required fields: {', '.join(sorted(missing))}")

    for field, expected in [
        ("type", str), ("version", str), ("request_id", str),
        ("timestamp", str), ("payload", dict),
    ]:
        error = _validate_field_type(field, message[field], expected)
        if error:
            return error

    if message["version"] != SUPPORTED_VERSION:
        return _build_error(102, f"Unsupported protocol version: {message['version']}")

    if message["type"] not in ALLOWED_TYPES:
        return _build_error(101, f"Unknown message type: {message['type']}")

    if not message["request_id"].strip():
        return _build_error(103, "request_id cannot be empty")

    try:
        datetime.fromisoformat(message["timestamp"].replace("Z", "+00:00"))
    except ValueError:
        return _build_error(100, "Invalid timestamp format (expected ISO 8601)")

    return None


async def _read_exact(reader: asyncio.StreamReader, n: int) -> bytes:
    """
    Czyta dokladnie n bajtow.
    Rzuca asyncio.IncompleteReadError jesli klient sie rozlaczyl.
    Rzuca asyncio.TimeoutError jesli minol FRAME_TIMEOUT.
    """
    return await asyncio.wait_for(reader.readexactly(n), timeout=FRAME_TIMEOUT)


async def parse_message(reader: asyncio.StreamReader) -> dict:
    """
    Parsuje wiadomosc z klienta.
    Rzuca IncompleteReadError lub TimeoutError jesli brak danych.
    Zwraca {"ok": True, "message": {...}} lub {"ok": False, "error_code": ..., "message": "..."}
    """
    # Czytaj naglowek (4 bajty - rozmiar)
    size_bytes = await _read_exact(reader, 4)
    message_size = int.from_bytes(size_bytes, byteorder="big")

    if message_size <= 0:
        return _build_error(100, "Invalid message size (must be > 0)")

    if message_size > MAX_MESSAGE_SIZE:
        return _build_error(105, f"Message too large: {message_size} bytes (max {MAX_MESSAGE_SIZE})")

    # Czytaj JSON
    json_bytes = await _read_exact(reader, message_size)

    try:
        message_dict = json.loads(json_bytes.decode("utf-8"))
    except json.JSONDecodeError as e:
        return _build_error(100, f"Invalid JSON: {str(e)}")
    except UnicodeDecodeError:
        return _build_error(100, "Invalid UTF-8 encoding")

    if not isinstance(message_dict, dict):
        return _build_error(100, "Message must be a JSON object")

    validation_error = _validate_message_structure(message_dict)
    if validation_error:
        return validation_error

    logger.debug("Parsed message: type=%s, request_id=%s", message_dict["type"], message_dict["request_id"])

    return {"ok": True, "message": message_dict}


def build_response(message_type: str, payload: dict, request_id: str = "") -> bytes:
    """Buduje length-prefixed JSON odpowiedz."""
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