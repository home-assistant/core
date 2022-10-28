"""Maico DataUpdateCoordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import httpx_client
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONNECTION_ERRORS
from .maico import Maico

_LOGGER = logging.getLogger(__name__)

# Matches iotwatt data log interval
REQUEST_REFRESH_DEFAULT_COOLDOWN = 5


class MaicoUpdater(DataUpdateCoordinator):
    """Class to manage fetching update data from the Maico Dual Flow Ventilation Device."""

    api: Maico | None = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize MaicoUpdater object."""
        self.entry = entry
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=entry.title,
            update_interval=timedelta(seconds=30),
            request_refresh_debouncer=Debouncer(
                hass,
                _LOGGER,
                cooldown=REQUEST_REFRESH_DEFAULT_COOLDOWN,
                immediate=True,
            ),
        )

    async def _async_update_data(self):
        """Fetch sensors from Maico device."""
        if self.api is None:
            api = Maico(
                device_name=self.entry.title,
                ip=self.entry.data[CONF_HOST],
                websession=httpx_client.get_async_client(self.hass),
                username=self.entry.data.get(CONF_USERNAME),
                password=self.entry.data.get(CONF_PASSWORD),
                # username=self.entry.data.get(CONF_USERNAME, "admin"),
                # password=self.entry.data.get(CONF_PASSWORD, ""),
            )
            try:
                is_authenticated = await api.connect()
            except CONNECTION_ERRORS as err:
                raise UpdateFailed("Connection failed") from err

            if not is_authenticated:
                raise UpdateFailed("Authentication error")

            self.api = api

        await self.api.update()
        return self.api.get_sensors()
