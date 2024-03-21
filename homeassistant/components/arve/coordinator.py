"""Coordinator for the Arve integration."""

from __future__ import annotations

from datetime import timedelta

from asyncarve import Arve, ArveConnectionError, ArveError, ArveSensProData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_SECRET, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class ArveCoordinator(DataUpdateCoordinator):
    """Arve coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize Arve coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            update_method=self._async_update_data,
        )

        self._client_session = async_get_clientsession(hass)

        self.arve = Arve(
            self.config_entry.data[CONF_ACCESS_TOKEN],
            self.config_entry.data[CONF_CLIENT_SECRET],
            self.config_entry.data[CONF_NAME],
            session=self._client_session,
        )

        self.first_refresh = True

    async def _async_update_data(self) -> ArveSensProData:
        """Fetch data from API endpoint."""
        if self.first_refresh:
            self.first_refresh = False
            try:
                await self.arve.get_sensor_info()
            except ArveConnectionError as exception:
                raise ConfigEntryError from exception
        try:
            response_data = await self.arve.device_sensor_data()
        except ArveConnectionError as err:
            raise UpdateFailed("Unable to connect to the Arve device") from err
        except ArveError as err:
            raise UpdateFailed("During the update, unknown error occurred") from err

        return response_data
