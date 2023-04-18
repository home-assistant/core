"""Tests for the lastfm sensor."""
from homeassistant.components.lastfm.const import STATE_NOT_SCROBBLING
from homeassistant.core import HomeAssistant

from tests.components.lastfm import MOCK_TRACK, create_entry, patch_interface


async def test_update_not_playing(hass: HomeAssistant) -> None:
    """Test update when no playing song."""
    entry = create_entry(hass)
    with patch_interface():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "sensor.lastfm_testaccount1"

    state = hass.states.get(entity_id)

    assert state.state == STATE_NOT_SCROBBLING


async def test_update_playing(hass: HomeAssistant) -> None:
    """Test update when song playing."""
    entry = create_entry(hass)
    with patch_interface(MOCK_TRACK):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "sensor.lastfm_testaccount1"

    state = hass.states.get(entity_id)

    assert state.state == "Goldband - Noodgeval"


async def test_state_attributes(hass: HomeAssistant) -> None:
    """Test update when song playing."""
    entry = create_entry(hass)
    with patch_interface():
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "sensor.lastfm_testaccount1"

    state = hass.states.get(entity_id)

    assert state.attributes["last_played"] == "Goldband - Noodgeval"
    assert state.attributes["top_played"] == "Goldband - Noodgeval"
    assert state.attributes["play_count"] == 1
