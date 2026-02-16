"""Test ViCare migration."""

from unittest.mock import patch

from serial import SerialException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


# Device migration test can be removed in 2025.4.0
async def test_device_not_connected(
    hass: HomeAssistant,
    # device_registry: dr.DeviceRegistry,
    # entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a config entry is not ready if the device is not connected."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "enocean.communicators.serialcommunicator.SerialCommunicator.__init__",
        side_effect=SerialException("Device not found"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
