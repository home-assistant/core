"""Test the api module."""
from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, call

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
    matter_client.commission_with_code.assert_called_once_with("12345678")

    matter_client.commission_with_code.reset_mock()
    matter_client.commission_with_code.side_effect = FailedCommand(
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
    matter_client.commission_with_code.assert_called_once_with("12345678")


async def test_commission_on_network(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
    matter_client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test the commission on network command."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/commission_on_network",
            "pin": "1234",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    matter_client.commission_on_network.assert_called_once_with("1234")

    matter_client.commission_on_network.reset_mock()
    matter_client.commission_on_network.side_effect = FailedCommand(
        "test_id", "test_code", "Failed to commission on network"
    )

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/commission_on_network",
            "pin": "1234",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "test_code"
    matter_client.commission_on_network.assert_called_once_with("1234")


async def test_set_wifi_credentials(
    hass: HomeAssistant,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
    matter_client: MagicMock,
    integration: MockConfigEntry,
) -> None:
    """Test the set WiFi credentials command."""
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {
            ID: 1,
            TYPE: "matter/set_wifi_credentials",
            "network_name": "test_network",
            "password": "test_password",
        }
    )
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert (
        matter_client.client.driver.device_controller.set_wifi_credentials.call_count
        == 1
    )
    assert (
        matter_client.client.driver.device_controller.set_wifi_credentials.call_args
        == call(ssid="test_network", credentials="test_password")
    )

    matter_client.client.driver.device_controller.set_wifi_credentials.reset_mock()
    matter_client.client.driver.device_controller.set_wifi_credentials.side_effect = (
        FailedCommand("test_id", "test_code", "Failed to commission on network")
    )

    await ws_client.send_json(
        {
            ID: 2,
            TYPE: "matter/set_wifi_credentials",
            "network_name": "test_network",
            "password": "test_password",
        }
    )
    msg = await ws_client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "test_code"
    assert (
        matter_client.client.driver.device_controller.set_wifi_credentials.call_count
        == 1
    )
    assert (
        matter_client.client.driver.device_controller.set_wifi_credentials.call_args
        == call(ssid="test_network", credentials="test_password")
    )
