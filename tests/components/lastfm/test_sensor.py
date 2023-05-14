"""Tests for the lastfm sensor."""

from pylast import Track

from homeassistant.components.lastfm.const import DOMAIN, STATE_NOT_SCROBBLING
from homeassistant.core import HomeAssistant

from . import CONF_DATA, MockNetwork, patch_fetch_user

from tests.common import MockConfigEntry


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
