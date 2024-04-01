"""Configure tests for the LastFM integration."""

from collections.abc import Awaitable, Callable
from typing import Generator
from unittest.mock import patch, AsyncMock

from pylast import Track, WSError, User
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



@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lastfm.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry

@pytest.fixture
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


@pytest.fixture
def imported_config_entry() -> MockConfigEntry:
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


@pytest.fixture
async def mock_lastfm_user(
    hass: HomeAssistant,
) -> Generator[AsyncMock, None, None]:
    """Fixture for setting up the component."""
    with (
        patch(
            "homeassistant.components.lastfm.User",
            autospec=True,
        ) as mock_user,
    ):
        user = mock_user.return_value

        yield user

@pytest.fixture
async def mock_lastfm_network(
    hass: HomeAssistant,
) -> Generator[AsyncMock, None, None]:
    """Fixture for setting up the component."""
    with (
        patch(
            "homeassistant.components.lastfm.config_flow.LastFMNetwork",
            autospec=True,
        ) as mock_network,
    ):
        network = mock_network.return_value

        network.get_user.return_value = AsyncMock(spec=User)

        yield network


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
