"""Coordinator for Chess.com."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from chess_com_api import ChessComAPIError, ChessComClient, Player, PlayerStats

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .puzzle_api import PuzzleStats, PuzzleStatsClient

_LOGGER = logging.getLogger(__name__)

type ChessConfigEntry = ConfigEntry[ChessCoordinator]


@dataclass
class ChessData:
    """Data for Chess.com."""

    player: Player
    stats: PlayerStats
    puzzle_stats: PuzzleStats | None


class ChessCoordinator(DataUpdateCoordinator[ChessData]):
    """Coordinator for Chess.com."""

    config_entry: ChessConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ChessConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=timedelta(hours=1),
        )
        session = async_get_clientsession(hass)
        self.client = ChessComClient(session=session)
        self.puzzle_client = PuzzleStatsClient(session=session)

    async def _async_update_data(self) -> ChessData:
        """Update data from Chess.com."""
        username = self.config_entry.data[CONF_USERNAME]
        try:
            player = await self.client.get_player(username)
            stats = await self.client.get_player_stats(username)
        except ChessComAPIError as err:
            raise UpdateFailed(f"Error communicating with Chess.com: {err}") from err

        puzzle_stats = await self.puzzle_client.async_get_puzzle_stats(username)

        return ChessData(player=player, stats=stats, puzzle_stats=puzzle_stats)
