"""Define an object to manage fetching NYT Games data."""

from dataclasses import dataclass
from datetime import timedelta
from typing import override

from nyt_games import (
    Connections,
    NYTGamesAuthenticationError,
    NYTGamesClient,
    NYTGamesError,
    SpellingBee,
    Wordle,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


@dataclass
class NYTGamesData:
    """Class for NYT Games data."""

    wordle: Wordle
    spelling_bee: SpellingBee | None
    connections: Connections | None


type NYTGamesConfigEntry = ConfigEntry[NYTGamesCoordinator]


class NYTGamesCoordinator(DataUpdateCoordinator[NYTGamesData]):
    """Class to manage fetching NYT Games data."""

    config_entry: NYTGamesConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NYTGamesConfigEntry,
        client: NYTGamesClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=config_entry,
            name="NYT Games",
            update_interval=timedelta(minutes=15),
        )
        self.client = client

    @override
    async def _async_update_data(self) -> NYTGamesData:
        try:
            stats_data = await self.client.get_latest_stats()
            connections_data = await self.client.get_connections()
        except NYTGamesAuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_error",
            ) from error
        except NYTGamesError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(error)},
            ) from error
        return NYTGamesData(
            wordle=stats_data.wordle,
            spelling_bee=stats_data.spelling_bee,
            connections=connections_data,
        )
