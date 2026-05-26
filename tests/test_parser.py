import json
import asyncio
import pytest
from datetime import datetime, timezone

from server.protocol.parser import parse_message, build_response, SUPPORTED_VERSION

# ── helpers ──────────────────────────────────────────────────────────────────

def make_reader(data: bytes) -> asyncio.StreamReader:
    """Tworzy strumień StreamReader w pamięci i wypełnia go danymi."""
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


def valid_message_dict() -> dict:
    """Zwraca poprawny słownik reprezentujący bazową wiadomość do testów."""
    return {
        "type": "HELLO",
        "version": SUPPORTED_VERSION,
        "request_id": "req-12345",
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "payload": {"client_name": "pytest"}
    }


def encode_message(msg_dict: dict | list | str) -> bytes:
    """Koduje słownik/obiekt do formatu [4 bajty rozmiar][JSON]."""
    json_bytes = json.dumps(msg_dict).encode("utf-8")
    size_bytes = len(json_bytes).to_bytes(4, byteorder="big")
    return size_bytes + json_bytes


# ==============================================================================

@pytest.mark.asyncio
class TestMessageParser:

    async def test_parses_valid_message(self):
        """Parser poprawnie czyta i akceptuje dobrze sformatowaną wiadomość."""
        msg = valid_message_dict()
        reader = make_reader(encode_message(msg))
        
        result = await parse_message(reader)
        
        assert result["ok"] is True
        assert result["message"]["type"] == "HELLO"
        assert result["message"]["request_id"] == "req-12345"

    async def test_rejects_missing_fields(self):
        """Parser odrzuca wiadomość, w której brakuje wymaganych pól."""
        msg = valid_message_dict()
        del msg["request_id"]  # Usuwamy wymagane pole
        reader = make_reader(encode_message(msg))
        
        result = await parse_message(reader)
        
        assert result["ok"] is False
        assert result["error_code"] == 103
        assert "Missing required fields: request_id" in result["message"]

    async def test_rejects_invalid_protocol_version(self):
        """Parser odrzuca wiadomość ze złą wersją protokołu."""
        msg = valid_message_dict()
        msg["version"] = "9.9"
        reader = make_reader(encode_message(msg))
        
        result = await parse_message(reader)
        
        assert result["ok"] is False
        assert result["error_code"] == 102
        assert "Unsupported protocol version" in result["message"]

    async def test_rejects_unknown_message_type(self):
        """Parser odrzuca typy wiadomości spoza zdefiniowanej listy ALLOWED_TYPES."""
        msg = valid_message_dict()
        msg["type"] = "HACK_THE_MAINFRAME"
        reader = make_reader(encode_message(msg))
        
        result = await parse_message(reader)
        
        assert result["ok"] is False
        assert result["error_code"] == 101
        assert "Unknown message type" in result["message"]

    async def test_rejects_empty_request_id(self):
        """Parser odrzuca puste pole request_id."""
        msg = valid_message_dict()
        msg["request_id"] = "   "
        reader = make_reader(encode_message(msg))
        
        result = await parse_message(reader)
        
        assert result["ok"] is False
        assert result["error_code"] == 103
        assert "request_id cannot be empty" in result["message"]

    async def test_rejects_invalid_timestamp(self):
        """Parser weryfikuje poprawność formatu ISO 8601 dla timestampów."""
        msg = valid_message_dict()
        msg["timestamp"] = "10 marca 2026 15:00"
        reader = make_reader(encode_message(msg))
        
        result = await parse_message(reader)
        
        assert result["ok"] is False
        assert result["error_code"] == 100
        assert "Invalid timestamp format" in result["message"]

    async def test_rejects_non_dict_json(self):
        """Wiadomość musi być słownikiem (obiektem), a nie listą czy stringiem."""
        reader = make_reader(encode_message(["jestem", "tablicą"]))
        
        result = await parse_message(reader)
        
        assert result["ok"] is False
        assert result["error_code"] == 100
        assert "must be a JSON object" in result["message"]

    async def test_rejects_malformed_json(self):
        """Próba parsowania uszkodzonego JSONa zwraca odpowiedni błąd."""
        broken_json = b'{"type": "HELLO", "version": "1.0"' # brak zamykającego nawiasu
        size_bytes = len(broken_json).to_bytes(4, byteorder="big")
        reader = make_reader(size_bytes + broken_json)
        
        result = await parse_message(reader)
        
        assert result["ok"] is False
        assert result["error_code"] == 100
        assert "Invalid JSON" in result["message"]

    async def test_rejects_message_too_large(self):
        """Parser chroni przed przepełnieniem (więcej niż MAX_MESSAGE_SIZE)."""
        # Fałszujemy nagłówek z deklaracją wielkości przekraczającą limit (np. 100 KB)
        huge_size = 100 * 1024
        size_bytes = huge_size.to_bytes(4, byteorder="big")
        reader = make_reader(size_bytes + b"{}")
        
        result = await parse_message(reader)
        
        assert result["ok"] is False
        assert result["error_code"] == 105
        assert "Message too large" in result["message"]


class TestResponseBuilder:

    def test_build_response_format(self):
        """Funkcja build_response prawidłowo pakuje payload i dodaje nagłówek."""
        payload = {"status": "success"}
        request_id = "req-123"
        
        raw_response = build_response("HELLO", payload, request_id)
        
        # Pierwsze 4 bajty to rozmiar
        size = int.from_bytes(raw_response[:4], byteorder="big")
        assert size == len(raw_response) - 4
        
        # Reszta to poprawny JSON
        decoded_json = json.loads(raw_response[4:].decode("utf-8"))
        
        assert decoded_json["type"] == "HELLO"
        assert decoded_json["version"] == SUPPORTED_VERSION
        assert decoded_json["request_id"] == "req-123"
        assert decoded_json["payload"] == payload
        assert "timestamp" in decoded_json