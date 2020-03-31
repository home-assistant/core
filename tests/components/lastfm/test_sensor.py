"""Tests for the lastfm sensor."""
import unittest
from unittest import mock
from homeassistant.components.lastfm.sensor import LastfmSensor
from pylast import LastFMNetwork, Track


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


class TestLastfmSensor(unittest.TestCase):
    """Unit test for LastfmSensor."""

    @mock.patch("pylast.LastFMNetwork.get_user")
    def test_update_not_playing(self, mock_lastfm_api_get_user):
        """Test update when no playing song."""
        mock_lastfm_api_get_user.return_value = MockUser(None)
        sensor = LastfmSensor("my-user", LastFMNetwork())
        sensor.update()

        self.assertEqual("Not Scrobbling", sensor._state)

    @mock.patch("pylast.LastFMNetwork.get_user")
    def test_update_playing(self, mock_lastfm_api_get_user):
        """Test update when song playing."""
        mock_lastfm_api_get_user.return_value = MockUser(Track("artist", "title", None))
        sensor = LastfmSensor("my-user", LastFMNetwork())
        sensor.update()

        self.assertEqual("artist - title", sensor._state)
