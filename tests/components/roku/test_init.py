"""Tests for the Roku integration."""
from unittest.mock import AsyncMock, MagicMock, patch

from rokuecp import RokuConnectionError

from homeassistant.components.roku.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@patch(
    "homeassistant.components.roku.coordinator.Roku._request",
    side_effect=RokuConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the Roku configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_no_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roku: AsyncMock,
) -> None:
    """Test the Roku configuration entry with missing unique id."""
    mock_config_entry.unique_id = None
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        hass.data[DOMAIN][mock_config_entry.entry_id].device_id
        == mock_config_entry.entry_id
    )


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_roku: AsyncMock,
) -> None:
    """Test the Roku configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
