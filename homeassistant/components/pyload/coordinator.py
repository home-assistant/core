"""Update coordinator for pyLoad Integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from pyloadapi import (
    CannotConnect,
    InvalidAuth,
    ParserError,
    PyLoadAPI,
    StatusServerResponse,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=20)


@dataclass(kw_only=True)
class pyLoadData:
    """Data from pyLoad."""

    status: StatusServerResponse
    free_space: int
    version: str


class PyLoadCoordinator(DataUpdateCoordinator[pyLoadData]):
    """pyLoad coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, pyload: PyLoadAPI) -> None:
        """Initialize pyLoad coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.pyload = pyload
        self.version: str

    async def _async_update_data(self) -> pyLoadData:
        """Fetch data from API endpoint."""
        try:
            if not self.version:
                self.version = await self.pyload.version()
            return pyLoadData(
                free_space=await self.pyload.free_space(),
                status=await self.pyload.get_status(),
                version=self.version,
            )
        except InvalidAuth:
            _LOGGER.debug("Authentication failed, trying to reauthenticate")
            try:
                await self.pyload.login()
            except InvalidAuth as e:
                raise ConfigEntryError(
                    f"Authentication failed for {self.pyload.username}, check your login credentials",
                ) from e
            else:
                raise UpdateFailed(
                    "Unable to retrieve data due to cookie expiration but re-authentication was successful."
                )
        except CannotConnect as e:
            raise UpdateFailed(
                "Unable to connect and retrieve data from pyLoad API"
            ) from e
        except ParserError as e:
            raise UpdateFailed("Unable to parse data from pyLoad API") from e
