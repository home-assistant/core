"""Common fixtures for the Lichess tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiolichess.models import LichessStatistics, LichessUser
import pytest

from homeassistant.components.lichess.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lichess.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="DrNykterstein",
        unique_id="drnykterstein",
        data={CONF_API_TOKEN: "my_secret_token"},
    )


@pytest.fixture
def mock_lichess_client() -> Generator[AsyncMock]:
    """Mock Lichess client."""
    with (
        patch(
            "homeassistant.components.lichess.coordinator.AioLichess",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.lichess.config_flow.AioLichess",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_all.return_value = LichessUser(
            id="drnykterstein",
            username="DrNykterstein",
            url="https://lichess.org/@/DrNykterstein",
            created_at=1420502920988,
            seen_at=1747342929853,
            play_time=999999,
        )
        client.get_user_id.return_value = "drnykterstein"
        client.get_statistics.return_value = LichessStatistics(
            ultra_bullet_rating=1500,
            ultra_bullet_games=2,
            bullet_rating=1373,
            bullet_games=7,
            blitz_rating=944,
            blitz_games=31,
            rapid_rating=1050,
            rapid_games=324,
            classical_rating=888,
            classical_games=1,
            correspondence_rating=1600,
            correspondence_games=5,
            chess960_rating=1700,
            chess960_games=10,
            crazyhouse_rating=1800,
            crazyhouse_games=15,
            antichess_rating=1900,
            antichess_games=20,
            atomic_rating=2000,
            atomic_games=25,
            horde_rating=2100,
            horde_games=30,
            king_of_the_hill_rating=2200,
            king_of_the_hill_games=35,
            racing_kings_rating=2300,
            racing_kings_games=40,
            three_check_rating=2400,
            three_check_games=45,
            puzzle_rating=2500,
            puzzle_games=50,
        )
        yield client
