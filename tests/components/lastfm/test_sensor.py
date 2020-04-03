"""Tests for the lastfm sensor."""
from unittest.mock import patch

from pylast import LastFMNetwork, Track

from homeassistant.components import sensor
from homeassistant.components.lastfm.sensor import STATE_NOT_SCROBBLING, LastfmSensor
from homeassistant.setup import async_setup_component


class MockUser:
    """Mock user object for pylast."""

    def __init__(self, now_playing_result):
        """Initialize the mock."""
        self._now_playing_result = now_playing_result

    def get_playcount(self):
        """Get mock play count."""
        return 1

    def get_image(self):
        """Get mock play count."""
        pass

    def get_recent_tracks(self, limit):
        """Get mock recent tracks."""
        return []

    def get_top_tracks(self, limit):
        """Get mock top tracks."""
        return []

    def get_now_playing(self):
        """Get mock now playing."""
        return self._now_playing_result


async def test_update_not_playing(hass):
    """Test update when no playing song."""

    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {"sensor": {"platform": "lastfm", "api_key": "secret-key", "users": ["test"],}},
    )

    entity_id = "sensor.lastfm_test"

    state = hass.states.get(entity_id)

    assert state == STATE_NOT_SCROBBLING

    with patch(
        ("pylast.LastFMNetwork.get_user"), return_value=MockUser(None),
    ):
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state == STATE_NOT_SCROBBLING


async def test_update_playing(hass):
    """Test update when song playing."""

    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {"sensor": {"platform": "lastfm", "api_key": "secret-key", "users": ["test"],}},
    )

    entity_id = "sensor.lastfm_test"

    state = hass.states.get(entity_id)

    assert state == STATE_NOT_SCROBBLING

    with patch(
        ("pylast.LastFMNetwork.get_user"),
        return_value=MockUser(Track("artist", "title", None)),
    ):
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state == "artist - title"
