"""DataUpdateCoordinator for anglian_water."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pyanglianwater import AnglianWater
from pyanglianwater.exceptions import (
    ExpiredAccessTokenError,
    InvalidPasswordError,
    InvalidUsernameError,
    ServiceUnavailableError,
    UnknownEndpointError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class AnglianWaterDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: AnglianWater,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=20),
        )
        self.client = client

    async def _async_update_data(self):
        """Update data via library."""
        try:
            await self.client.update()
        except (InvalidUsernameError, InvalidPasswordError) as exception:
            raise ConfigEntryError(exception) from exception
        except (UnknownEndpointError, ServiceUnavailableError) as exception:
            raise UpdateFailed(exception) from exception
        except ExpiredAccessTokenError:
            await self.client.api.refresh_login()
            await self.client.update()
