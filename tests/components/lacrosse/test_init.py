"""Tests for the LaCrosse integration setup."""

from unittest.mock import MagicMock, patch

from serial import SerialException

from homeassistant.components.lacrosse.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceRegistry

from tests.common import MockConfigEntry

ENTRY_DATA = {
    "device": "/dev/ttyUSB0",
    "baud": 57600,
    "datarate": 57600,
    "frequency": 868.3,
    "led": True,
    "toggle_interval": 5,
    "toggle_mask": 255,
    "sensors": {
        "outdoor_temperature": {
            "id": 1,
            "type": "temperature",
            "expire_after": 300,
            "unique_id": "outdoor_temperature_unique",
        }
    },
}


async def test_setup_and_unload(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setting up and unloading a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    receiver = MagicMock()

    with patch(
        "homeassistant.components.lacrosse.pylacrosse.LaCrosse",
        return_value=receiver,
    ) as mock_lacrosse:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED
        mock_lacrosse.assert_called_once_with("/dev/ttyUSB0", 57600)
        receiver.open.assert_called_once()
        receiver.led_mode_state.assert_called_once_with(True)
        receiver.set_frequency.assert_called_once_with(868.3)
        receiver.set_datarate.assert_called_once_with(57600)
        receiver.set_toggle_interval.assert_called_once_with(5)
        receiver.set_toggle_mask.assert_called_once_with(255)
        receiver.start_scan.assert_called_once()
        receiver.register_callback.assert_called_once()

        entity_entry = entity_registry.async_get("sensor.outdoor_temperature")
        assert entity_entry is not None
        assert entity_entry.unique_id == "outdoor_temperature_unique"

        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, "/dev/ttyUSB0_1"), entry.entry_id
        )
        assert device is not None
        assert entity_entry.device_id == device.id

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert receiver.close.call_count == 1


async def test_setup_serial_error(hass: HomeAssistant) -> None:
    """Test that an unavailable receiver retries setup."""
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lacrosse.pylacrosse.LaCrosse"
    ) as mock_lacrosse:
        mock_lacrosse.side_effect = SerialException("unavailable")
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
