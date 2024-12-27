"""Update coordinator for Tile."""

from datetime import timedelta

from pytile.api import API
from pytile.errors import InvalidAuthError, SessionExpiredError, TileError
from pytile.tile import Tile

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import LOGGER


class TileCoordinator(DataUpdateCoordinator[None]):
    """Define an object to coordinate Tile data retrieval."""

    def __init__(self, hass: HomeAssistant, client: API, tile: Tile) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=tile.name,
            update_interval=timedelta(minutes=2),
        )
        self.tile = tile
        self.client = client

    async def _async_update_data(self) -> None:
        """Update data via library."""
        try:
            await self.tile.async_update()
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        except SessionExpiredError:
            LOGGER.debug("Tile session expired; creating a new one")
            await self.client.async_init()
        except TileError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err
