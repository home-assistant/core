"""Tests for the Chess.com puzzle API client."""

from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest

from homeassistant.components.chess_com.puzzle_api import PuzzleStats, PuzzleStatsClient


@pytest.fixture
def puzzle_stats_data() -> dict:
    """Return sample puzzle stats API response."""
    return {
        "statsInfo": {
            "gameCount": 150,
            "stats": {
                "rating": 1735,
                "passed_count": 100,
                "failed_count": 50,
            },
        }
    }


async def test_from_dict(puzzle_stats_data: dict) -> None:
    """Test PuzzleStats.from_dict parses correctly."""
    stats = PuzzleStats.from_dict(puzzle_stats_data)
    assert stats.rating == 1735
    assert stats.game_count == 150
    assert stats.passed_count == 100
    assert stats.failed_count == 50


async def test_get_puzzle_stats_success(puzzle_stats_data: dict) -> None:
    """Test successful puzzle stats fetch."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock()
    mock_response.json = AsyncMock(return_value=puzzle_stats_data)

    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_context

    client = PuzzleStatsClient(mock_session)
    result = await client.async_get_puzzle_stats("testuser")

    assert result is not None
    assert result.rating == 1735
    assert result.game_count == 150
    assert result.passed_count == 100
    assert result.failed_count == 50
    mock_session.get.assert_called_once()


async def test_get_puzzle_stats_client_error() -> None:
    """Test puzzle stats fetch returns None on ClientError."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(
        side_effect=aiohttp.ClientError("Connection error")
    )
    mock_context.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_context

    client = PuzzleStatsClient(mock_session)
    result = await client.async_get_puzzle_stats("testuser")

    assert result is None


async def test_get_puzzle_stats_timeout() -> None:
    """Test puzzle stats fetch returns None on timeout."""
    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(side_effect=TimeoutError)
    mock_context.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_context

    client = PuzzleStatsClient(mock_session)
    result = await client.async_get_puzzle_stats("testuser")

    assert result is None


async def test_get_puzzle_stats_invalid_data() -> None:
    """Test puzzle stats fetch returns None on invalid data."""
    mock_response = AsyncMock()
    mock_response.raise_for_status = Mock()
    mock_response.json = AsyncMock(return_value={"invalid": "data"})

    mock_session = AsyncMock(spec=aiohttp.ClientSession)
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_response)
    mock_context.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = mock_context

    client = PuzzleStatsClient(mock_session)
    result = await client.async_get_puzzle_stats("testuser")

    assert result is None
