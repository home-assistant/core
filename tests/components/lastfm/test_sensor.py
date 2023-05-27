"""Tests for the lastfm sensor."""
from pylast import Track, WSError

from homeassistant.components.lastfm.const import (
    ATTR_LAST_PLAYED,
    ATTR_PLAY_COUNT,
    ATTR_TOP_PLAYED,
    CONF_USERS,
    DOMAIN,
    STATE_NOT_SCROBBLING,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import API_KEY, CONF_DATA, USERNAME_1, MockNetwork, patch_fetch_user

from tests.common import MockConfigEntry

LEGACY_CONFIG = {
    Platform.SENSOR: [
        {CONF_PLATFORM: DOMAIN, CONF_API_KEY: API_KEY, CONF_USERS: [USERNAME_1]}
    ]
}


async def test_legacy_migration(hass: HomeAssistant) -> None:
    """Test migration from yaml to config flow."""
    with patch_fetch_user(None):
        assert await async_setup_component(hass, Platform.SENSOR, LEGACY_CONFIG)
        await hass.async_block_till_done()
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED
    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == 1


async def test_user_unavailable(hass: HomeAssistant) -> None:
    """Test update when user can't be fetched."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=CONF_DATA)
    entry.add_to_hass(hass)
    with patch_fetch_user(thrown_error=WSError("network", "status", "User not found")):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "sensor.testaccount1"

    state = hass.states.get(entity_id)

    assert state.state == "unavailable"


async def test_first_time_user(hass: HomeAssistant) -> None:
    """Test first time user."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=CONF_DATA)
    entry.add_to_hass(hass)
    with patch_fetch_user(first_time_user=True):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    entity_id = "sensor.testaccount1"

    state = hass.states.get(entity_id)

    assert state.state == STATE_NOT_SCROBBLING
    assert state.attributes[ATTR_LAST_PLAYED] is None
    assert state.attributes[ATTR_TOP_PLAYED] is None
    assert state.attributes[ATTR_PLAY_COUNT] == 1


async def test_update_not_playing(hass: HomeAssistant) -> None:
    """Test update when no playing song."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=CONF_DATA)
    entry.add_to_hass(hass)
    with patch_fetch_user(None):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    entity_id = "sensor.testaccount1"

    state = hass.states.get(entity_id)

    assert state.state == STATE_NOT_SCROBBLING


async def test_update_playing(hass: HomeAssistant) -> None:
    """Test update when playing a song."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=CONF_DATA)
    entry.add_to_hass(hass)
    with patch_fetch_user(Track("artist", "title", MockNetwork("test"))):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    entity_id = "sensor.testaccount1"

    state = hass.states.get(entity_id)

    assert state.state == "artist - title"
    assert state.attributes[ATTR_LAST_PLAYED] == "artist - title"
    assert state.attributes[ATTR_TOP_PLAYED] == "artist - title"
    assert state.attributes[ATTR_PLAY_COUNT] == 1
