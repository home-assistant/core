"""Define an object to manage fetching NYT Games data."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from nyt_games import NYTGamesClient, NYTGamesError, Wordle

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER

if TYPE_CHECKING:
    from . import NYTGamesConfigEntry


class NYTGamesCoordinator(DataUpdateCoordinator[Wordle]):
    """Class to manage fetching NYT Games data."""

    config_entry: NYTGamesConfigEntry

    def __init__(self, hass: HomeAssistant, client: NYTGamesClient) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name="NYT Games",
            update_interval=timedelta(minutes=15),
        )
        self.client = client

    async def _async_update_data(self) -> Wordle:
        try:
            return (await self.client.get_latest_stats()).stats.wordle
        except NYTGamesError as error:
            raise UpdateFailed(error) from error
