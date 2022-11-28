"""Test the api module."""
from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock

from aiohttp import ClientWebSocketResponse
from matter_server.client.exceptions import FailedCommand

from homeassistant.components.matter.api import ID, TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_commission(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
    matter_client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test the commission command."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/commission",
            "code": "12345678",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.commission.assert_called_once_with("12345678")

    matter_client.commission.reset_mock()
    matter_client.commission.side_effect = FailedCommand(
        "test_id", "test_code", "Failed to commission"
    )

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/commission",
            "code": "12345678",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "test_code"
    matter_client.commission.assert_called_once_with("12345678")
