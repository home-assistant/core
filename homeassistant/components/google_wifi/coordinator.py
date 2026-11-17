"""The Google Wifi integration coordinator."""

from datetime import timedelta
from typing import override

from googlewifiapi import GoogleWifiAPI, GoogleWifiStatus
from googlewifiapi.exception import GoogleWifiClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type GoogleWifiConfigEntry = ConfigEntry[GoogleWifiCoordinator]


class GoogleWifiCoordinator(DataUpdateCoordinator[GoogleWifiStatus]):
    """Coordinates entities for one Google Wifi device."""

    config_entry: GoogleWifiConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GoogleWifiConfigEntry,
        api: GoogleWifiAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.api = api

    @override
    async def _async_update_data(self) -> GoogleWifiStatus:
        """Fetch data from the API."""
        try:
            return await self.api.async_update()
        except GoogleWifiClientError as err:
            raise UpdateFailed("Unable to fetch Google Wifi status") from err
