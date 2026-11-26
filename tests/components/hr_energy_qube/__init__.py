"""Tests for the Qube Heat Pump integration."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.typing import WebSocketGenerator
from python_qube_heatpump import QubeDeviceInfo

from homeassistant.core import HomeAssistant


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Qube Heat Pump integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def async_shared_connections(
    hass_ws_client: WebSocketGenerator,
) -> list[tuple[list[str | int], dict[str, list[int]]]]:
    """Return the endpoint and units of each shared Modbus connection."""
    client = await hass_ws_client()
    await client.send_json_auto_id({"type": "modbus/connections/list"})
    response = await client.receive_json()
    assert response["success"]
    return [
        (connection["endpoint"], connection["units"])
        for connection in response["result"]["connections"]
    ]


DEVICE_INFO = QubeDeviceInfo(
    uuid="000100000007B5EA",
    software_version="4.1.00",
    controller_firmware="v5.1.007",
    project_name="DEQSIHPB000CR",
)
