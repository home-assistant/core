"""Tests for the Entur public transport integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.entur_public_transport.const import (
    CONF_EXPAND_PLATFORMS,
    CONF_NUMBER_OF_DEPARTURES,
    CONF_OMIT_NON_BOARDING,
    CONF_WHITELIST_LINES,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant

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
) -> None:
    """Test unloading of config entry."""
    # Verify the entry is loaded and entities exist
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify entity has valid state before unload
    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None
    assert state.state != "unavailable"

    # Unload the entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the entry is unloaded
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_entur_client")
async def test_reload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
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


@pytest.mark.usefixtures("mock_entur_client")
async def test_options_update_triggers_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that updating options triggers a reload and applies new settings."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify initial state - show_on_map is False, so no coordinates
    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None
    assert CONF_LATITUDE not in state.attributes
    assert CONF_LONGITUDE not in state.attributes

    # Update options to enable show_on_map
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            CONF_EXPAND_PLATFORMS: True,
            CONF_SHOW_ON_MAP: True,  # Changed from False to True
            CONF_WHITELIST_LINES: [],
            CONF_OMIT_NON_BOARDING: True,
            CONF_NUMBER_OF_DEPARTURES: 2,
        },
    )
    await hass.async_block_till_done()

    # Verify entry is still loaded after options update triggered reload
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify the new settings are applied - coordinates should now be present
    state = hass.states.get("sensor.entur_bergen_stasjon")
    assert state is not None
    assert state.attributes.get(CONF_LATITUDE) == 60.39032
    assert state.attributes.get(CONF_LONGITUDE) == 5.33396


async def test_setup_entry_expand_quays(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_entur_client: MagicMock,
) -> None:
    """Test that expand_all_quays is called when expand_platforms is True."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_entur_client.expand_all_quays.assert_called_once()


async def test_setup_entry_no_expand_quays(
    hass: HomeAssistant,
    mock_entur_client: MagicMock,
) -> None:
    """Test that expand_all_quays is not called when expand_platforms is False."""
    entry = MockConfigEntry(
        domain="entur_public_transport",
        title="Entur",
        data={
            "stop_ids": ["NSR:StopPlace:548"],
            "expand_platforms": False,  # Disabled
            "show_on_map": False,
            "line_whitelist": [],
            "omit_non_boarding": True,
            "number_of_departures": 2,
        },
        unique_id="NSR:StopPlace:548",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_entur_client.expand_all_quays.assert_not_called()
