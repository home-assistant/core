"""The tests for lastfm."""
from datetime import datetime
from unittest.mock import patch

from pylast import Album, PlayedTrack, Track

from homeassistant.components.lastfm.const import CONF_USERS, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

API_KEY = "asdasdasdasdasd"
USERNAME_1 = "testaccount1"

CONF_USER_INPUT = {CONF_API_KEY: API_KEY, CONF_USERS: USERNAME_1}

CONF_DATA = {**CONF_USER_INPUT, CONF_USERS: [CONF_USER_INPUT[CONF_USERS]]}


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add config entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        unique_id=USERNAME_1,
    )
    entry.add_to_hass(hass)
    return entry


class MockUser:
    """Mock User object for pylast."""

    def __init__(self, now_playing_result: dict | None = None) -> None:
        """Initialize the mock."""
        self._now_playing_result = now_playing_result

    def get_playcount(self) -> int | float:
        """Get mock play count."""
        return 1

    def get_image(self, size: int) -> str:
        """Get mock image."""
        return "yes"

    def get_recent_tracks(self, limit: int) -> list[PlayedTrack]:
        """Get mock recent tracks."""
        return [
            PlayedTrack(
                Track("asd", "yes", "network", "username"),
                Album("yes", "yes", {}, "username"),
                datetime.now(),
                datetime.now(),
            )
        ]

    def get_top_tracks(self, limit: int) -> list[dict]:
        """Get mock top tracks."""
        return []

    def get_now_playing(self):
        """Get mock now playing."""
        return self._now_playing_result


def patch_interface() -> MockUser:
    """Patch interface."""
    return patch("pylast.User", return_value=MockUser())
