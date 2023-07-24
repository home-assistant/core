"""The tests for lastfm."""
from unittest.mock import patch

from pylast import PyLastError, Track

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

    def __init__(self, username: str) -> None:
        """Initialize the mock."""
        self.username = username


class MockTopTrack:
    """Mock TopTrack object for pylast."""

    def __init__(self, item: Track) -> None:
        """Initialize the mock."""
        self.item = item


class MockLastTrack:
    """Mock LastTrack object for pylast."""

    def __init__(self, track: Track) -> None:
        """Initialize the mock."""
        self.track = track


class MockUser:
    """Mock User object for pylast."""

    def __init__(
        self,
        username: str = USERNAME_1,
        now_playing_result: Track | None = None,
        thrown_error: Exception | None = None,
        friends: list = [],
        recent_tracks: list[Track] = [],
        top_tracks: list[Track] = [],
    ) -> None:
        """Initialize the mock."""
        self._now_playing_result = now_playing_result
        self._thrown_error = thrown_error
        self._friends = friends
        self._recent_tracks = recent_tracks
        self._top_tracks = top_tracks
        self.name = username

    def get_name(self, capitalized: bool) -> str:
        """Get name of the user."""
        return self.name

    def get_playcount(self) -> int:
        """Get mock play count."""
        if self._thrown_error:
            raise self._thrown_error
        return len(self._recent_tracks)

    def get_image(self) -> str:
        """Get mock image."""
        return ""

    def get_recent_tracks(self, limit: int) -> list[MockLastTrack]:
        """Get mock recent tracks."""
        return [MockLastTrack(track) for track in self._recent_tracks]

    def get_top_tracks(self, limit: int) -> list[MockTopTrack]:
        """Get mock top tracks."""
        return [MockTopTrack(track) for track in self._recent_tracks]

    def get_now_playing(self) -> Track:
        """Get mock now playing."""
        return self._now_playing_result

    def get_friends(self) -> list[any]:
        """Get mock friends."""
        if len(self._friends) == 0:
            raise PyLastError("network", "status", "Page not found")
        return self._friends


def patch_user(user: MockUser) -> MockUser:
    """Patch interface."""
    return patch("pylast.User", return_value=user)


def patch_setup_entry() -> bool:
    """Patch interface."""
    return patch("homeassistant.components.lastfm.async_setup_entry", return_value=True)
