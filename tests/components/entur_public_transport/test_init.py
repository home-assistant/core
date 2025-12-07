"""Tests for the Entur public transport integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_integration")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test unloading of config entry."""
    # Verify the entry is loaded and entities exist
    assert mock_config_entry.state is ConfigEntryState.LOADED

    entities_before = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities_before) > 0

    # Verify entity has valid state before unload
    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None
    assert state.state != "unavailable"

    # Unload the entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the entry is unloaded
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    # Verify entity state is unavailable after unload
    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None
    assert state.state == "unavailable"


async def test_reload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
) -> None:
    """Test reloading of config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Reload the entry
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the entry is still loaded after reload
    assert mock_config_entry.state is ConfigEntryState.LOADED
