"""The WittIOT integration coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp.client_exceptions import ClientConnectorError
from wittiot import API
from wittiot.errors import WittiotError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class WittiotDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold WittIOT data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        ip: str,
    ) -> None:
        """Initialize."""
        self.ip = ip
        self.api = API(ip, session=async_get_clientsession(hass))
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=10)
        )

    async def _async_update_data(self) -> dict[str, str | float | int]:
        """Update data."""
        res = {}
        try:
            res = await self.api.request_loc_allinfo()
        except (WittiotError, ClientConnectorError) as error:
            raise UpdateFailed(error) from error
        _LOGGER.debug("Get device data: %s", res)
        return res
