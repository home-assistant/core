"""Tests for the Debug console websocket API."""

from typing import Any

import pytest

from homeassistant.components.debug_console.const import DOMAIN
from homeassistant.components.websocket_api import ERR_NOT_ALLOWED, ERR_UNAUTHORIZED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import COMMANDS, SESSION_ID, async_execute

from tests.common import MockConfigEntry, MockUser
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.mark.parametrize("command", COMMANDS)
async def test_requires_admin(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    command: dict[str, Any],
) -> None:
    """Test the console is only available to administrators."""
    hass_admin_user.groups = []

    await websocket_client.send_json_auto_id(command)

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_UNAUTHORIZED


@pytest.mark.parametrize("command", COMMANDS)
async def test_disabled_without_config_entry(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, command: dict[str, Any]
) -> None:
    """Test the console refuses commands until enabled by a config entry."""
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(command)

    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_ALLOWED


async def test_disabled_by_unloading(
    hass: HomeAssistant,
    websocket_client: MockHAClientWebSocket,
    setup_integration: MockConfigEntry,
) -> None:
    """Test unloading the config entry disables the console."""
    result = await async_execute(websocket_client, "answer = 42\nanswer")

    assert result["result"] == {"type": "number", "value": "42"}

    assert await hass.config_entries.async_unload(setup_integration.entry_id)

    await websocket_client.send_json_auto_id(
        {"type": "debug_console/execute", "session_id": SESSION_ID, "code": "1"}
    )
    msg = await websocket_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == ERR_NOT_ALLOWED

    # Closing the connection of a closed session is fine.
    await websocket_client.close()
    await hass.async_block_till_done()
