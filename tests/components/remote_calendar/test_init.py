"""Tests for init platform of Remote Calendar."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import TEST_ENTITY

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_httpx_client: AsyncMock
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(TEST_ENTITY)
    assert state
    assert state.state == "off"

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
