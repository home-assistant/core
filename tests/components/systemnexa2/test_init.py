"""Test the System Nexa 2 integration setup and unload."""

from unittest.mock import AsyncMock, MagicMock

from sn2 import DeviceInitializationError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test loading and unloading the integration."""
    mock_config_entry.add_to_hass(hass)

    device = mock_system_nexa_2_device.return_value

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries()) == 1

    device.connect.assert_called_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    device.disconnect.assert_called_once()


async def test_setup_failure_device_initialization_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_system_nexa_2_device: MagicMock,
) -> None:
    """Test setup failure when device initialization fails."""
    mock_config_entry.add_to_hass(hass)

    mock_system_nexa_2_device.initiate_device = AsyncMock(
        side_effect=DeviceInitializationError("Test error")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
