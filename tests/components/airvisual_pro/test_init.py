"""Test AirVisual Pro setup."""

from unittest.mock import Mock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_device_registry_connection(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    pro: Mock,
) -> None:
    """Test the device is registered with its MAC address as a network connection."""
    with patch("homeassistant.components.airvisual_pro.NodeSamba", return_value=pro):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    assert (
        dr.CONNECTION_NETWORK_MAC,
        "12:34:56:78:90:ab",
    ) in devices[0].connections
