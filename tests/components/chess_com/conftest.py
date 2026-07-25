"""Common fixtures for the Chess.com tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from chess_com_api import Player, PlayerStats
import pytest

from homeassistant.components.chess_com.const import DOMAIN
from homeassistant.const import CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.chess_com.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Joost",
        unique_id="532748851",
        data={CONF_USERNAME: "joostlek"},
    )


@pytest.fixture
def mock_chess_client() -> Generator[AsyncMock]:
    """Mock Chess.com client."""
    with (
        patch(
            "homeassistant.components.chess_com.coordinator.ChessComClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.chess_com.config_flow.ChessComClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        player_data = load_json_object_fixture("player.json", DOMAIN)
        client.get_player.return_value = Player.from_dict(player_data)
        stats_data = load_json_object_fixture("stats.json", DOMAIN)
        client.get_player_stats.return_value = PlayerStats.from_dict(stats_data)
        yield client
