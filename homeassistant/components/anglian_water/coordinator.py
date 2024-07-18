"""DataUpdateCoordinator for anglian_water."""

from __future__ import annotations

from datetime import timedelta

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
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class AnglianWaterDataUpdateCoordinator(DataUpdateCoordinator):
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
        self.client: AnglianWater = client

    async def _async_update_data(self, token_refreshed: bool = False):
        """Update data via library."""
        try:
            await self.client.update()
        except InvalidUsernameError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except InvalidPasswordError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except UnknownEndpointError as exception:
            raise UpdateFailed(exception) from exception
        except ServiceUnavailableError as exception:
            raise UpdateFailed(exception) from exception
        except ExpiredAccessTokenError as exception:
            if not token_refreshed:
                await self.client.api.refresh_login()
                await self._async_update_data(True)
            else:
                raise UpdateFailed(exception) from exception
