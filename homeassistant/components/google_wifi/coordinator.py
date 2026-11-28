"""The Google Wifi integration coordinator."""

from datetime import timedelta
from typing import TYPE_CHECKING, override

from googlewifiapi import GoogleWifiAPI, GoogleWifiStatus
from googlewifiapi.exception import GoogleWifiClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from . import GoogleWifiConfigEntry


class GoogleWifiCoordinator(DataUpdateCoordinator[GoogleWifiStatus]):
    """Coordinates entities for the Google Wifi integration."""

    # pyrefly: ignore[bad-override-mutable-attribute]
    config_entry: GoogleWifiConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoogleWifiConfigEntry,
        api: GoogleWifiAPI,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
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
