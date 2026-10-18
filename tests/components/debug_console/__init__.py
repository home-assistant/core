"""Tests for the Debug console integration."""

from typing import Any

import pytest

from homeassistant.components.websocket_api import TYPE_RESULT

from tests.typing import MockHAClientWebSocket

SESSION_ID = "test-session"

# Every command, with valid arguments.
COMMANDS = [
    pytest.param(
        {"type": "debug_console/execute", "session_id": SESSION_ID, "code": "1"},
        id="execute",
    ),
    pytest.param(
        {"type": "debug_console/inspect", "session_id": SESSION_ID, "object_id": "x"},
        id="inspect",
    ),
    pytest.param(
        {
            "type": "debug_console/get_attribute",
            "session_id": SESSION_ID,
            "object_id": "x",
            "attribute": "x",
        },
        id="get_attribute",
    ),
    pytest.param(
        {"type": "debug_console/complete", "session_id": SESSION_ID, "code": "x"},
        id="complete",
    ),
    pytest.param(
        {"type": "debug_console/signature", "session_id": SESSION_ID, "code": "x("},
        id="signature",
    ),
    pytest.param({"type": "debug_console/clear", "session_id": SESSION_ID}, id="clear"),
    pytest.param({"type": "debug_console/stop", "session_id": SESSION_ID}, id="stop"),
    pytest.param({"type": "debug_console/check_input", "code": "1"}, id="check_input"),
    pytest.param({"type": "debug_console/info"}, id="info"),
    pytest.param({"type": "debug_console/warning/accept"}, id="warning_accept"),
]

# The commands that need the warning accepted, on release versions.
CONSOLE_COMMANDS = [
    command for command in COMMANDS if command.id not in ("info", "warning_accept")
]


async def async_send(
    websocket_client: MockHAClientWebSocket, command: dict[str, Any]
) -> Any:
    """Send a command with the test session, and return its result."""
    await websocket_client.send_json_auto_id({"session_id": SESSION_ID, **command})

    msg = await websocket_client.receive_json()
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    return msg["result"]


async def async_execute(
    websocket_client: MockHAClientWebSocket, code: str, **kwargs: Any
) -> dict[str, Any]:
    """Execute code in the console, and return the result."""
    return await async_send(
        websocket_client, {"type": "debug_console/execute", "code": code, **kwargs}
    )


async def async_inspect(
    websocket_client: MockHAClientWebSocket, object_id: str
) -> dict[str, Any]:
    """Inspect an object in the console, and return its children."""
    return await async_send(
        websocket_client, {"type": "debug_console/inspect", "object_id": object_id}
    )
