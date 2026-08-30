"""Tests for the LaCrosse integration setup."""

from unittest.mock import MagicMock, patch

from serial import SerialException

from homeassistant.components.lacrosse.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTRY_DATA = {
    "device": "/dev/ttyUSB0",
    "baud": 57600,
    "sensors": {
        "outdoor_temperature": {
            "id": 1,
            "type": "temperature",
            "expire_after": 300,
        }
    },
}


async def test_setup_and_unload(hass: HomeAssistant) -> None:
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
        receiver.start_scan.assert_called_once()
        receiver.register_callback.assert_called_once()

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
