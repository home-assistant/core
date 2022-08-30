"""Support for Ecowitt Weather Station Service."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
import async_timeout
from ecpat1 import API
from ecpat1.errors import EcowittError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_APP_KEY, CONF_IP, CONF_MAC, CONNECTION_TYPE, DOMAIN, LOCAL

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ecowitt Weather from a config entry."""

    websession = async_get_clientsession(hass)
    update_interval = timedelta(seconds=60)

    if entry.data.get(CONNECTION_TYPE) == LOCAL:
        if not entry.unique_id:
            hass.config_entries.async_update_entry(entry, unique_id=entry.data[CONF_IP])
        coordinator = EcowittDataUpdateCoordinator(
            hass, entry, websession, "", "", "", entry.data[CONF_IP], update_interval
        )
    else:
        if not entry.unique_id:
            hass.config_entries.async_update_entry(
                entry, unique_id=entry.data[CONF_APP_KEY]
            )
        coordinator = EcowittDataUpdateCoordinator(
            hass,
            entry,
            websession,
            entry.data[CONF_API_KEY],
            entry.data[CONF_APP_KEY],
            entry.data[CONF_MAC],
            "",
            update_interval,
        )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class EcowittDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold Ecowit data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: ClientSession,
        api_key: str,
        app_key: str,
        mac: str,
        ip: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.api_key = api_key
        self.app_key = app_key
        self.mac = mac
        self.ip = ip
        self.entry = entry
        self.ecoapi = API(app_key, api_key, ip, session=session)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> dict[str, str | float | int]:
        res = {}
        async with async_timeout.timeout(10):
            try:
                if self.entry.data.get(CONNECTION_TYPE) == LOCAL:
                    res = await self.ecoapi.request_loc_allinfo()
                    return res
                res = await self.ecoapi.get_data_real_time(self.mac)
                return res
            except (EcowittError, ClientConnectorError) as error:
                raise UpdateFailed(error) from error
