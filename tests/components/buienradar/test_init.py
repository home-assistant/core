"""Tests for the buienradar component."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_integration


@pytest.mark.usefixtures("mock_buienradar_data")
async def test_load_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading a config entry."""
    entry = await setup_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retry_when_fetch_fails(
    hass: HomeAssistant, mock_buienradar_data: AsyncMock
) -> None:
    """Test setup is retried when the first update fails."""
    mock_buienradar_data.side_effect = UpdateFailed("Unable to retrieve data")

    entry = await setup_integration(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY
