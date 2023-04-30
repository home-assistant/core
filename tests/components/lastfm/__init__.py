"""The tests for lastfm."""
from unittest.mock import patch

from pylast import Track

from homeassistant.components.lastfm.const import CONF_USERS
from homeassistant.const import CONF_API_KEY

API_KEY = "asdasdasdasdasd"
USERNAME_1 = "testaccount1"

CONF_DATA = {CONF_API_KEY: API_KEY, CONF_USERS: [USERNAME_1]}


class MockNetwork:
    """Mock _Network object for pylast."""

    def __init__(self, username: str):
        """Initialize the mock."""
        self.username = username


class MockUser:
    """Mock User object for pylast."""

    def __init__(self, now_playing_result):
        """Initialize the mock."""
        self._now_playing_result = now_playing_result
        self.name = "test"

    def get_playcount(self):
        """Get mock play count."""
        return 1

    def get_image(self):
        """Get mock image."""

    def get_recent_tracks(self, limit):
        """Get mock recent tracks."""
        return []

    def get_top_tracks(self, limit):
        """Get mock top tracks."""
        return []

    def get_now_playing(self):
        """Get mock now playing."""
        return self._now_playing_result


def patch_fetch_user(now_playing: Track | None = None) -> MockUser:
    """Patch interface."""
    return patch("pylast.User", return_value=MockUser(now_playing))


def patch_setup_entry() -> bool:
    """Patch interface."""
    return patch("homeassistant.components.lastfm.async_setup_entry", return_value=True)
