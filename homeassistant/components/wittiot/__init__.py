"""The Wittiot integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
from wittiot import API
from wittiot.errors import WittiotError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_IP, CONNECTION_TYPE, DOMAIN, LOCAL

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wittiot from a config entry."""

    websession = async_get_clientsession(hass)
    update_interval = timedelta(seconds=60)
    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=entry.data[CONF_IP])
    coordinator = WittiotDataUpdateCoordinator(
        hass, entry, websession, entry.data[CONF_IP], update_interval
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class WittiotDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Ecowit data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: ClientSession,
        ip: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.ip = ip
        self.entry = entry
        self.api = API(ip, session=session)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[str, str | float | int]:
        """Update data."""
        res = {}
        async with asyncio.timeout(10):
            try:
                if self.entry.data.get(CONNECTION_TYPE) == LOCAL:
                    res = await self.api.request_loc_allinfo()
                    _LOGGER.info("Get device data: %s", res)
                    return res

            except (WittiotError, ClientConnectorError) as error:
                raise UpdateFailed(error) from error
        return res
