"""The tests for lastfm."""
from unittest.mock import patch

from pylast import Track, WSError

from homeassistant.components.lastfm.const import CONF_MAIN_USER, CONF_USERS
from homeassistant.const import CONF_API_KEY

API_KEY = "asdasdasdasdasd"
USERNAME_1 = "testaccount1"
USERNAME_2 = "testaccount2"

CONF_DATA = {
    CONF_API_KEY: API_KEY,
    CONF_MAIN_USER: USERNAME_1,
    CONF_USERS: [USERNAME_1, USERNAME_2],
}
CONF_USER_DATA = {CONF_API_KEY: API_KEY, CONF_MAIN_USER: USERNAME_1}
CONF_FRIENDS_DATA = {CONF_USERS: [USERNAME_2]}


class MockNetwork:
    """Mock _Network object for pylast."""

    def __init__(self, username: str):
        """Initialize the mock."""
        self.username = username


class MockUser:
    """Mock User object for pylast."""

    def __init__(self, now_playing_result, error, has_friends, username):
        """Initialize the mock."""
        self._now_playing_result = now_playing_result
        self._thrown_error = error
        self._has_friends = has_friends
        self.name = username

    def get_name(self, capitalized: bool) -> str:
        """Get name of the user."""
        return self.name

    def get_playcount(self):
        """Get mock play count."""
        if self._thrown_error:
            raise self._thrown_error
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

    def get_friends(self):
        """Get mock friends."""
        if self._has_friends is False:
            raise WSError("network", "status", "Page not found")
        return [MockUser(None, None, True, USERNAME_2)]


def patch_fetch_user(
    now_playing: Track | None = None,
    thrown_error: Exception | None = None,
    has_friends: bool = True,
    username: str = USERNAME_1,
) -> MockUser:
    """Patch interface."""
    return patch(
        "pylast.User",
        return_value=MockUser(now_playing, thrown_error, has_friends, username),
    )


def patch_setup_entry() -> bool:
    """Patch interface."""
    return patch("homeassistant.components.lastfm.async_setup_entry", return_value=True)
