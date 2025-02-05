"""Tests for the deako component init."""

from unittest.mock import MagicMock

from pydeako import FindDevicesError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_deako_async_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    pydeako_deako_mock: MagicMock,
    pydeako_discoverer_mock: MagicMock,
) -> None:
    """Test successful setup entry."""
    pydeako_deako_mock.return_value.get_devices.return_value = {
        "id1": {},
        "id2": {},
    }

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    pydeako_deako_mock.assert_called_once_with(
        pydeako_discoverer_mock.return_value.get_address
    )
    pydeako_deako_mock.return_value.connect.assert_called_once()
    pydeako_deako_mock.return_value.find_devices.assert_called_once()
    pydeako_deako_mock.return_value.get_devices.assert_called()

    assert mock_config_entry.runtime_data == pydeako_deako_mock.return_value


async def test_deako_async_setup_entry_devices_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    pydeako_deako_mock: MagicMock,
    pydeako_discoverer_mock: MagicMock,
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady when pydeako raises DeviceListTimeout."""

    mock_config_entry.add_to_hass(hass)

    pydeako_deako_mock.return_value.find_devices.side_effect = FindDevicesError()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    pydeako_deako_mock.assert_called_once_with(
        pydeako_discoverer_mock.return_value.get_address
    )
    pydeako_deako_mock.return_value.connect.assert_called_once()
    pydeako_deako_mock.return_value.find_devices.assert_called_once()
    pydeako_deako_mock.return_value.disconnect.assert_called_once()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
