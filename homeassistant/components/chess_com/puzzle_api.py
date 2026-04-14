"""Client for fetching Chess.com puzzle statistics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientSession

PUZZLE_STATS_URL = (
    "https://www.chess.com/callback/stats/tactics2/new/puzzles/{username}"
)


@dataclass(frozen=True)
class PuzzleStats:
    """Puzzle statistics for a Chess.com player."""

    rating: int
    game_count: int
    passed_count: int
    failed_count: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PuzzleStats:
        """Create PuzzleStats from API response."""
        stats_info = data["statsInfo"]
        stats = stats_info["stats"]
        return cls(
            rating=stats["rating"],
            game_count=stats_info["gameCount"],
            passed_count=stats["passed_count"],
            failed_count=stats["failed_count"],
        )


class PuzzleStatsClient:
    """Client for fetching puzzle stats from Chess.com."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the puzzle stats client."""
        self._session = session

    async def async_get_puzzle_stats(self, username: str) -> PuzzleStats | None:
        """Fetch puzzle stats for a player."""
        url = PUZZLE_STATS_URL.format(username=username)
        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                return PuzzleStats.from_dict(data)
        except ClientError, TimeoutError, KeyError, TypeError, ValueError:
            return None
