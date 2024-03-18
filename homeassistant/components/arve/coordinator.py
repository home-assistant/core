"""Coordinator for the Arve integration."""

from __future__ import annotations

from datetime import timedelta

from asyncarve import Arve, ArveConnectionError, ArveError, ArveSensProData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class ArveCoordinator(DataUpdateCoordinator):
    """Arve coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, arve: Arve) -> None:
        """Initialize Arve coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            update_method=self._async_update_data,
        )
        self.arve = arve

    async def _async_update_data(self) -> ArveSensProData:
        """Fetch data from API endpoint."""
        try:
            response_data = await self.arve.device_sensor_data()
        except ArveConnectionError as err:
            raise UpdateFailed("Unable to connect to the Arve device") from err
        except ArveError as err:
            raise UpdateFailed("During the update, unknown error occurred") from err

        return response_data
