"""Configure tests for the LastFM integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pylast import LastFMNetwork, Track, User
import pytest

from homeassistant.components.lastfm.const import CONF_MAIN_USER, CONF_USERS, DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.lastfm import API_KEY, USERNAME_1, USERNAME_2, MockUser


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
) -> AsyncMock:
    """Fixture for setting up the component."""
    user = AsyncMock(spec=User)

    network = AsyncMock(spec=LastFMNetwork)
    network.username = "testaccount1"

    user.get_now_playing.return_value = Track("artist", "title", network)
    user.return_value.get_top_tracks.return_value = [Track("artist", "title", network)]
    user.return_value.get_recent_tracks.return_value = [
        Track("artist", "title", network)
    ]
    user.get_friends.return_value = [MockUser()]
    user.get_playcount.return_value = 1
    user.get_image.return_value = "image"
    user.get_name.return_value = "testaccount1"
    user.name = "testaccount1"

    return user


@pytest.fixture
async def mock_lastfm_network(
    hass: HomeAssistant,
    mock_lastfm_user: AsyncMock,
) -> Generator[AsyncMock, None, None]:
    """Fixture for setting up the component."""
    with (
        patch(
            "homeassistant.components.lastfm.config_flow.LastFMNetwork",
            autospec=True,
        ) as mock_network,
        patch(
            "homeassistant.components.lastfm.coordinator.LastFMNetwork",
            new=mock_network,
        ),
    ):
        network = mock_network.return_value

        network.get_user.return_value = mock_lastfm_user

        yield network
