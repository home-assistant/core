"""Coordinator for the WattTime integration."""

from __future__ import annotations

from datetime import timedelta

from aiowatttime import Client
from aiowatttime.emissions import RealTimeEmissionsResponseType
from aiowatttime.errors import InvalidCredentialsError, WattTimeError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=5)


class WattTimeCoordinator(DataUpdateCoordinator[RealTimeEmissionsResponseType]):
    """Coordinator for WattTime data updates."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: Client,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=DEFAULT_UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> RealTimeEmissionsResponseType:
        """Get the latest realtime emissions data."""
        try:
            return await self.client.emissions.async_get_realtime_emissions(
                self.config_entry.data[CONF_LATITUDE],
                self.config_entry.data[CONF_LONGITUDE],
            )
        except InvalidCredentialsError as err:
            raise ConfigEntryAuthFailed("Invalid username/password") from err
        except WattTimeError as err:
            raise UpdateFailed(
                f"Error while requesting data from WattTime: {err}"
            ) from err
