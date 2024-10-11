"""NYTGames tests configuration."""

from collections.abc import Generator
from unittest.mock import patch

from nyt_games.models import ConnectionsStats, WordleStats
import pytest

from homeassistant.components.nyt_games.const import DOMAIN
from homeassistant.const import CONF_TOKEN

from tests.common import MockConfigEntry, load_fixture
from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nyt_games.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nyt_games_client() -> Generator[AsyncMock]:
    """Mock an NYTGames client."""
    with (
        patch(
            "homeassistant.components.nyt_games.NYTGamesClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.nyt_games.config_flow.NYTGamesClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_latest_stats.return_value = WordleStats.from_json(
            load_fixture("latest.json", DOMAIN)
        ).player.stats
        client.get_user_id.return_value = 218886794
        client.get_connections.return_value = ConnectionsStats.from_json(
            load_fixture("connections.json", DOMAIN)
        ).player.stats
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="NYTGames",
        data={CONF_TOKEN: "token"},
        unique_id="218886794",
    )
