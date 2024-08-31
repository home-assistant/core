"""Tests for the Luftdaten integration."""
from unittest.mock import AsyncMock, MagicMock, patch

from luftdaten.exceptions import LuftdatenError

from homeassistant.components.luftdaten.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luftdaten: AsyncMock,
) -> None:
    """Test the Luftdaten configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@patch(
    "homeassistant.components.luftdaten.Luftdaten.get_data",
    side_effect=LuftdatenError,
)
async def test_config_entry_not_ready(
    mock_get_data: MagicMock,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Luftdaten configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_get_data.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_not_ready_no_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luftdaten: MagicMock,
) -> None:
    """Test the Luftdaten configuration entry not ready."""
    mock_luftdaten.values = {}
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_luftdaten.get_data.assert_called()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setting_unique_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_luftdaten: MagicMock
) -> None:
    """Test we set unique ID if not set yet."""
    mock_config_entry.unique_id = None
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.unique_id == "12345"
