"""Heatzy platform coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from heatzypy import HeatzyClient
from heatzypy.exception import AuthenticationFailed, HeatzyException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DEBOUNCE_COOLDOWN, DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = 60


class HeatzyDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to fetch datas."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Class to manage fetching Heatzy data API."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=DEBOUNCE_COOLDOWN, immediate=False
            ),
        )
        self.api = HeatzyClient(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            async_create_clientsession(hass),
        )

    async def _async_update_data(self) -> dict:
        """Update data."""
        try:
            async with async_timeout.timeout(API_TIMEOUT):
                return await self.api.async_get_devices()
        except AuthenticationFailed as error:
            raise ConfigEntryAuthFailed() from error
        except HeatzyException as error:
            raise UpdateFailed(error) from error
