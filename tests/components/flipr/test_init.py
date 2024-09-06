"""Tests for init methods."""

import logging
from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test unload entry."""

    mock_flipr_client.search_all_ids.return_value = {
        "flipr": ["myfliprid"],
        "hub": ["hubid"],
    }

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_duplicate_config_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_entry_dup: MockConfigEntry,
    mock_flipr_client: AsyncMock,
) -> None:
    """Test duplicate config entries."""

    _LOGGER.debug("mock_config_entry = %s", mock_config_entry)
    _LOGGER.debug("mock_config_entry_dup = %s", mock_config_entry_dup)

    _LOGGER.debug("SETTING FIST ENTRY")
    mock_config_entry.add_to_hass(hass)
    # Initialize the first entry with default mock
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Initialize the second entry with another flipr id
    _LOGGER.debug("SETTING SECOND ENTRY")
    mock_config_entry_dup.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry_dup.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry_dup.state is ConfigEntryState.SETUP_ERROR
