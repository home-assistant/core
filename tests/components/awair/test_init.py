"""Test Awair init."""
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_awair
from .const import LOCAL_CONFIG, LOCAL_UNIQUE_ID


async def test_local_awair_sensors(
    hass: HomeAssistant, local_devices, local_data, device_registry: dr.DeviceRegistry
) -> None:
    """Test expected sensors on a local Awair."""
    fixtures = [local_devices, local_data]
    entry = await setup_awair(hass, fixtures, LOCAL_UNIQUE_ID, LOCAL_CONFIG)

    device_entry = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    assert device_entry.name == "Mock Title"

    with patch("python_awair.AwairClient.query", side_effect=fixtures):
        hass.config_entries.async_update_entry(entry, title="Hello World")
        await hass.async_block_till_done()

    device_entry = device_registry.async_get(device_entry.id)
    assert device_entry.name == "Hello World"
