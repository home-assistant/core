import unittest
from unittest import mock
from homeassistant.components.lastfm.sensor import LastfmSensor
from pylast import LastFMNetwork, Track


class MockUser:
    def __init__(self, now_playing_result):
        self._now_playing_result = now_playing_result

    def get_playcount(self):
        return 1

    def get_image(self):
        pass

    def get_recent_tracks(self, limit):
        return []

    def get_top_tracks(self, limit):
        return []

    def get_now_playing(self):
        return self._now_playing_result


class TestLastfmSensor(unittest.TestCase):
    @mock.patch("pylast.LastFMNetwork.get_user")
    def test_update_not_playing(self, mock_lastfm_api_get_user):
        mock_lastfm_api_get_user.return_value = MockUser(None)
        sensor = LastfmSensor("my-user", LastFMNetwork())
        sensor.update()

        self.assertEqual("Not Scrobbling", sensor._state)

    @mock.patch("pylast.LastFMNetwork.get_user")
    def test_update_playing(self, mock_lastfm_api_get_user):
        mock_lastfm_api_get_user.return_value = MockUser(Track("artist", "title", None))
        sensor = LastfmSensor("my-user", LastFMNetwork())
        sensor.update()

        self.assertEqual("artist - title", sensor._state)
