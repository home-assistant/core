"""Tests for the Home Assistant Websocket API."""
from unittest.mock import Mock, patch

from aiohttp import WSMsgType
import voluptuous as vol

from homeassistant.components.websocket_api import (
    async_register_command,
    const,
    messages,
)
from homeassistant.core import HomeAssistant


async def test_invalid_message_format(websocket_client) -> None:
    """Test sending invalid JSON."""
    await websocket_client.send_json({"type": 5})

    msg = await websocket_client.receive_json()

    assert msg["type"] == const.TYPE_RESULT
    error = msg["error"]
    assert error["code"] == const.ERR_INVALID_FORMAT
    assert error["message"].startswith("Message incorrectly formatted")


async def test_invalid_json(websocket_client) -> None:
    """Test sending invalid JSON."""
    await websocket_client.send_str("this is not JSON")

    msg = await websocket_client.receive()

    assert msg.type == WSMsgType.close


async def test_quiting_hass(hass: HomeAssistant, websocket_client) -> None:
    """Test sending invalid JSON."""
    with patch.object(hass.loop, "stop"):
        await hass.async_stop()

    msg = await websocket_client.receive()

    assert msg.type == WSMsgType.CLOSED


async def test_unknown_command(websocket_client) -> None:
    """Test get_panels command."""
    await websocket_client.send_json({"id": 5, "type": "unknown_command"})

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_UNKNOWN_COMMAND


async def test_handler_failing(hass: HomeAssistant, websocket_client) -> None:
    """Test a command that raises."""
    async_register_command(
        hass,
        "bla",
        Mock(side_effect=TypeError),
        messages.BASE_COMMAND_MESSAGE_SCHEMA.extend({"type": "bla"}),
    )
    await websocket_client.send_json({"id": 5, "type": "bla"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_UNKNOWN_ERROR


async def test_invalid_vol(hass: HomeAssistant, websocket_client) -> None:
    """Test a command that raises invalid vol error."""
    async_register_command(
        hass,
        "bla",
        Mock(side_effect=TypeError),
        messages.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {"type": "bla", vol.Required("test_config"): str}
        ),
    )

    await websocket_client.send_json({"id": 5, "type": "bla", "test_config": 5})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_INVALID_FORMAT
    assert "expected str for dictionary value" in msg["error"]["message"]
