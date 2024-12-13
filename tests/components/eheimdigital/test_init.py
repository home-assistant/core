"""Tests for the init module."""

from unittest.mock import MagicMock

from eheimdigital.types import EheimDeviceType

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_remove_device(
    hass: HomeAssistant,
    eheimdigital_hub_mock: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test removing a device."""
    assert await async_setup_component(hass, "config", {})
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await eheimdigital_hub_mock.call_args.kwargs["device_found_callback"](
        "00:00:00:00:00:01", EheimDeviceType.VERSION_EHEIM_CLASSIC_LED_CTRL_PLUS_E
    )
    await hass.async_block_till_done()

    mac_address: str = eheimdigital_hub_mock.return_value.main.mac_address

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac_address)},
    )
    assert device_entry is not None

    hass_client = await hass_ws_client(hass)

    # Do not allow to delete a connected device
    response = await hass_client.remove_device(
        device_entry.id, mock_config_entry.entry_id
    )
    assert not response["success"]

    eheimdigital_hub_mock.return_value.devices = {}

    # Allow to delete a not connected device
    response = await hass_client.remove_device(
        device_entry.id, mock_config_entry.entry_id
    )
    assert response["success"]
