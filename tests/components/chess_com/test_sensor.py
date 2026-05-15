"""Tests for the Chess.com sensor."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from chess_com_api import Player, PlayerStats
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.chess_com.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_load_json_object_fixture,
    load_json_object_fixture,
    snapshot_platform,
)


@pytest.fixture
def mock_chess_client_no_puzzles() -> Generator[AsyncMock]:
    """Mock Chess.com client with puzzle stats returning None."""
    with (
        patch(
            "homeassistant.components.chess_com.coordinator.ChessComClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.chess_com.config_flow.ChessComClient",
            new=mock_client,
        ),
        patch(
            "homeassistant.components.chess_com.coordinator.PuzzleStatsClient",
            autospec=True,
        ) as mock_puzzle_client,
    ):
        client = mock_client.return_value
        player_data = load_json_object_fixture("player.json", DOMAIN)
        client.get_player.return_value = Player.from_dict(player_data)
        stats_data = load_json_object_fixture("stats.json", DOMAIN)
        client.get_player_stats.return_value = PlayerStats.from_dict(stats_data)

        puzzle_client = mock_puzzle_client.return_value
        puzzle_client.async_get_puzzle_stats.return_value = None

        yield client


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_chess_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.chess_com._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_daily_only(
    hass: HomeAssistant,
    mock_chess_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that entities for unplayed game modes are not created."""
    mock_chess_client.get_player_stats.return_value = PlayerStats.from_dict(
        await async_load_json_object_fixture(hass, "stats_daily_only.json", DOMAIN)
    )
    with patch("homeassistant.components.chess_com._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.joost_rapid_chess_rating") is None
    assert hass.states.get("sensor.joost_bullet_chess_rating") is None
    assert hass.states.get("sensor.joost_blitz_chess_rating") is None
    assert hass.states.get("sensor.joost_daily_chess960_rating") is None


async def test_puzzle_stats_unavailable(
    hass: HomeAssistant,
    mock_chess_client_no_puzzles: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test puzzle sensors return None when puzzle stats are unavailable."""
    with patch("homeassistant.components.chess_com._PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.joost_puzzle_rating")
    assert state is not None
    assert state.state == "unknown"
