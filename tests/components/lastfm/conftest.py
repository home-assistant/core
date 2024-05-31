"""Configure tests for the LastFM integration."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from pylast import Track, WSError
import pytest

from homeassistant.components.lastfm.const import CONF_MAIN_USER, CONF_USERS, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.lastfm import (
    API_KEY,
    USERNAME_1,
    USERNAME_2,
    MockNetwork,
    MockUser,
)

type ComponentSetup = Callable[[MockConfigEntry, MockUser], Awaitable[None]]


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create LastFM entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_API_KEY: API_KEY,
            CONF_MAIN_USER: USERNAME_1,
            CONF_USERS: [USERNAME_1, USERNAME_2],
        },
    )


@pytest.fixture(name="imported_config_entry")
def mock_imported_config_entry() -> MockConfigEntry:
    """Create LastFM entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_API_KEY: API_KEY,
            CONF_MAIN_USER: None,
            CONF_USERS: [USERNAME_1, USERNAME_2],
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
) -> Callable[[MockConfigEntry, MockUser], Awaitable[None]]:
    """Fixture for setting up the component."""

    async def func(mock_config_entry: MockConfigEntry, mock_user: MockUser) -> None:
        mock_config_entry.add_to_hass(hass)
        with patch("pylast.User", return_value=mock_user):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()

    return func


@pytest.fixture(name="default_user")
def mock_default_user() -> MockUser:
    """Return default mock user."""
    return MockUser(
        now_playing_result=Track("artist", "title", MockNetwork("lastfm")),
        top_tracks=[Track("artist", "title", MockNetwork("lastfm"))],
        recent_tracks=[Track("artist", "title", MockNetwork("lastfm"))],
        friends=[MockUser()],
    )


@pytest.fixture(name="default_user_no_friends")
def mock_default_user_no_friends() -> MockUser:
    """Return default mock user without friends."""
    return MockUser(
        now_playing_result=Track("artist", "title", MockNetwork("lastfm")),
        top_tracks=[Track("artist", "title", MockNetwork("lastfm"))],
        recent_tracks=[Track("artist", "title", MockNetwork("lastfm"))],
    )


@pytest.fixture(name="first_time_user")
def mock_first_time_user() -> MockUser:
    """Return first time mock user."""
    return MockUser(now_playing_result=None, top_tracks=[], recent_tracks=[])


@pytest.fixture(name="not_found_user")
def mock_not_found_user() -> MockUser:
    """Return not found mock user."""
    return MockUser(thrown_error=WSError("network", "status", "User not found"))
