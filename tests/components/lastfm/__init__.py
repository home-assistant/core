"""The tests for lastfm."""

import asyncio
from typing import Any
from unittest.mock import patch

from pylast import PyLastError, Track

from homeassistant.components.lastfm.const import (
    CONF_API_SECRET,
    CONF_MAIN_USER,
    CONF_SESSION_KEY,
    CONF_USERS,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

API_KEY = "asdasdasdasdasd"
API_SECRET = "testapisecret"
SESSION_KEY = "testsessionkey"
NEW_SESSION_KEY = "newtestsessionkey"
AUTH_TOKEN = "testauthtoken"
AUTH_URL = f"https://www.last.fm/api/auth/?api_key={API_KEY}&token={AUTH_TOKEN}"
USERNAME_1 = "testaccount1"
USERNAME_2 = "testaccount2"

CONF_DATA = {
    CONF_API_KEY: API_KEY,
    CONF_MAIN_USER: USERNAME_1,
    CONF_USERS: [USERNAME_1, USERNAME_2],
}
CONF_DATA_WITH_SESSION_KEY = {
    CONF_API_KEY: API_KEY,
    CONF_API_SECRET: API_SECRET,
    CONF_MAIN_USER: USERNAME_1,
    CONF_SESSION_KEY: SESSION_KEY,
    CONF_USERS: [USERNAME_1, USERNAME_2],
}
CONF_USER_DATA = {CONF_API_KEY: API_KEY, CONF_MAIN_USER: USERNAME_1}
CONF_USER_DATA_WITH_SECRET = {
    CONF_API_KEY: API_KEY,
    CONF_API_SECRET: API_SECRET,
    CONF_MAIN_USER: USERNAME_1,
}
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
        recent_tracks_error: Exception | None = None,
        friends: list | UndefinedType = UNDEFINED,
        recent_tracks: list[Track] | UndefinedType = UNDEFINED,
        top_tracks: list[Track] | UndefinedType = UNDEFINED,
    ) -> None:
        """Initialize the mock."""
        self._now_playing_result = now_playing_result
        self._thrown_error = thrown_error
        self._recent_tracks_error = recent_tracks_error
        self._friends = [] if friends is UNDEFINED else friends
        self._recent_tracks = [] if recent_tracks is UNDEFINED else recent_tracks
        self._top_tracks = [] if top_tracks is UNDEFINED else top_tracks
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
        return "image"

    def get_recent_tracks(self, limit: int) -> list[MockLastTrack]:
        """Get mock recent tracks."""
        if self._recent_tracks_error:
            raise PyLastError from self._recent_tracks_error
        return [MockLastTrack(track) for track in self._recent_tracks]

    def get_top_tracks(self, limit: int) -> list[MockTopTrack]:
        """Get mock top tracks."""
        return [MockTopTrack(track) for track in self._recent_tracks]

    def get_now_playing(self) -> Track:
        """Get mock now playing."""
        if self._recent_tracks_error:
            raise self._recent_tracks_error
        return self._now_playing_result

    def get_friends(self) -> list[Any]:
        """Get mock friends."""
        if len(self._friends) == 0:
            raise PyLastError("network", "status", "Page not found")
        return self._friends


class MockSessionKeyGenerator:
    """Mock SessionKeyGenerator object for pylast."""

    def __init__(
        self,
        web_auth_url_error: Exception | None = None,
        session_key_error: Exception | None = None,
        session_key: str = SESSION_KEY,
        session_username: str = USERNAME_1,
    ) -> None:
        """Initialize the mock."""
        self.web_auth_url_error = web_auth_url_error
        self.session_key_error = session_key_error
        self.session_key = session_key
        self.session_username = session_username

    def get_web_auth_url(self) -> str:
        """Get mock web auth URL."""
        if self.web_auth_url_error:
            raise self.web_auth_url_error
        return AUTH_URL

    def get_web_auth_session_key_username(
        self, url: str, token: str = ""
    ) -> tuple[str, str]:
        """Get mock session key and username."""
        if self.session_key_error:
            raise self.session_key_error
        return self.session_key, self.session_username

    def get_web_auth_session_key(self, url: str, token: str = "") -> str:
        """Get mock session key."""
        session_key, _username = self.get_web_auth_session_key_username(url, token)
        return session_key


def patch_user(user: MockUser) -> MockUser:
    """Patch interface."""
    return patch("pylast.User", return_value=user)


def patch_setup_entry() -> bool:
    """Patch interface."""
    return patch("homeassistant.components.lastfm.async_setup_entry", return_value=True)


def get_session_key_polling_task() -> asyncio.Task[None]:
    """Return the active session key polling task."""
    return next(
        task
        for task in asyncio.all_tasks()
        if task.get_coro().__qualname__
        == "LastFmConfigFlowHandler._async_poll_for_session_key"
    )
