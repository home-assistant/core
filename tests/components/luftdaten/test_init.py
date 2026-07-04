"""Tests for the Luftdaten integration."""

from unittest.mock import MagicMock

from luftdaten.exceptions import LuftdatenConnectionError, LuftdatenError
import pytest

from homeassistant.components.luftdaten.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_luftdaten: MagicMock,
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


@pytest.mark.parametrize("side_effect", [LuftdatenConnectionError, LuftdatenError])
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_luftdaten: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test the Luftdaten configuration entry not ready."""
    mock_luftdaten.get_data.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_luftdaten.get_data.call_count == 1
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
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=None)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.unique_id == "12345"
