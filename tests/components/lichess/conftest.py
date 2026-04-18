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
        unique_id="drnykterstien",
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
            id="drnykterstien",
            username="DrNykterstein",
            url="https://lichess.org/@/DrNykterstein",
            created_at=1420502920988,
            seen_at=1747342929853,
            play_time=999999,
        )
        client.get_user_id.return_value = "drnykterstien"
        client.get_statistics.return_value = LichessStatistics(
            blitz_rating=944,
            rapid_rating=1050,
            bullet_rating=1373,
            classical_rating=888,
            blitz_games=31,
            rapid_games=324,
            bullet_games=7,
            classical_games=1,
        )
        yield client
