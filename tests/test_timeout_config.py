import asyncio

import client.network.connection as connection_module
from client.network.connection import (
    ConnectionManager,
    KEEP_ALIVE_IDLE_SECONDS,
    MAX_PING_FAILURES,
    MESSAGE_ASSEMBLY_TIMEOUT,
    REQUEST_TIMEOUT_SECONDS,
)
from client.network.session_manager import SESSION_IDLE_TIMEOUT
from server import server
from server.protocol.parser import FRAME_TIMEOUT
from server.security.security_config import SESSION_RESUME_MINUTES


def test_protocol_timeout_constants_match_stage_1_documentation():
    assert REQUEST_TIMEOUT_SECONDS == 5.0
    assert FRAME_TIMEOUT == 3
    assert MESSAGE_ASSEMBLY_TIMEOUT == 3.0
    assert SESSION_IDLE_TIMEOUT == 60.0
    assert server.IDLE_TIMEOUT == 60
    assert KEEP_ALIVE_IDLE_SECONDS == 30.0
    assert MAX_PING_FAILURES == 2
    assert SESSION_RESUME_MINUTES == 5


def test_keep_alive_disconnects_after_two_failed_pings(monkeypatch):
    manager = ConnectionManager()
    manager.is_connected = True
    manager._last_activity_time = 0.0
    closed = False

    async def no_sleep(_seconds):
        return None

    async def close_sockets():
        nonlocal closed
        closed = True
        manager.is_connected = False

    async def failing_ping():
        raise TimeoutError("missing PONG")

    async def on_disconnect():
        return None

    monkeypatch.setattr(connection_module.asyncio, "sleep", no_sleep)
    manager.close_sockets = close_sockets
    manager.on_unexpected_disconnect = on_disconnect

    asyncio.run(manager._keep_alive_loop(failing_ping))

    assert closed is True
