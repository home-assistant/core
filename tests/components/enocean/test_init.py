"""Test the EnOcean integration."""

from unittest.mock import patch

from homeassistant.components.enocean.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from . import MOCK_SERIAL_BY_ID, MOCK_USB_DEVICE, MODULE

from tests.common import MockConfigEntry


async def test_device_not_connected(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a config entry is not ready if the device is not connected."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        f"{MODULE}.Gateway.start",
        side_effect=ConnectionError("Device not found"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


# Config entry migration can be removed in 2026.10.0
async def test_config_entity_migration_from_v1_1_to_v1_2(
    hass: HomeAssistant,
) -> None:
    """Test that the config entry is updated correctly."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={
            CONF_DEVICE: MOCK_USB_DEVICE.device,
        },
    )
    mock_config_entry.add_to_hass(hass)

    assert mock_config_entry.unique_id is None

    with (
        patch(
            f"{MODULE}.get_serial_by_id",
            return_value=MOCK_SERIAL_BY_ID,
        ),
        patch(
            f"{MODULE}.usb_device_from_path",
            return_value=MOCK_USB_DEVICE,
        ) as mock_usb_device_from_path,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Migration should have added unique_id to entry data
    assert mock_usb_device_from_path.call_count == 1
    assert mock_config_entry.version == 1
    assert mock_config_entry.minor_version == 2
    assert mock_config_entry.data[CONF_DEVICE] == MOCK_SERIAL_BY_ID
    assert mock_config_entry.unique_id == "0403:6001_1234_EnOcean GmbH_USB 300"
