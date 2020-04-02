"""Tests for the lastfm sensor."""
from unittest.mock import patch

from pylast import LastFMNetwork, Track

from homeassistant.components.lastfm.sensor import LastfmSensor


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


@patch("pylast.LastFMNetwork.get_user")
def test_update_not_playing(mock_lastfm_api_get_user):
    """Test update when no playing song."""
    mock_lastfm_api_get_user.return_value = MockUser(None)
    sensor = LastfmSensor("my-user", LastFMNetwork())
    sensor.update()

    assert sensor._state == "Not Scrobbling"


@patch("pylast.LastFMNetwork.get_user")
def test_update_playing(mock_lastfm_api_get_user):
    """Test update when song playing."""
    mock_lastfm_api_get_user.return_value = MockUser(Track("artist", "title", None))
    sensor = LastfmSensor("my-user", LastFMNetwork())
    sensor.update()

    assert sensor._state == "artist - title"
