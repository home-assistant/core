"""The Vilfo Router integration."""
import asyncio
from datetime import timedelta
import logging

from vilfo import Client as VilfoClient
from vilfo.exceptions import VilfoException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import Throttle

from .const import ATTR_BOOT_TIME, ATTR_LOAD, DOMAIN, ROUTER_DEFAULT_HOST

PLATFORMS = ["sensor"]

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Vilfo Router from a config entry."""
    host = entry.data[CONF_HOST]
    access_token = entry.data[CONF_ACCESS_TOKEN]

    vilfo_router = VilfoRouterData(hass, host, access_token)

    await vilfo_router.async_update()

    if not vilfo_router.available:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = vilfo_router

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class VilfoRouterData:
    """Define an object to hold sensor data."""

    def __init__(self, hass, host, access_token):
        """Initialize."""
        self._vilfo = VilfoClient(host, access_token)
        self.hass = hass
        self.host = host
        self.available = False
        self.firmware_version = None
        self.mac_address = self._vilfo.mac
        self.data = {}
        self._unavailable_logged = False

    @property
    def unique_id(self):
        """Get the unique_id for the Vilfo Router."""
        if self.mac_address:
            return self.mac_address

        if self.host == ROUTER_DEFAULT_HOST:
            return self.host

        return self.host

    def _fetch_data(self):
        board_information = self._vilfo.get_board_information()
        load = self._vilfo.get_load()

        return {
            "board_information": board_information,
            "load": load,
        }

    @Throttle(DEFAULT_SCAN_INTERVAL)
    async def async_update(self):
        """Update data using calls to VilfoClient library."""
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)

            self.firmware_version = data["board_information"]["version"]
            self.data[ATTR_BOOT_TIME] = data["board_information"]["bootTime"]
            self.data[ATTR_LOAD] = data["load"]

            self.available = True
        except VilfoException as error:
            if not self._unavailable_logged:
                _LOGGER.error(
                    "Could not fetch data from %s, error: %s", self.host, error
                )
                self._unavailable_logged = True
            self.available = False
            return

        if self.available and self._unavailable_logged:
            _LOGGER.info("Vilfo Router %s is available again", self.host)
            self._unavailable_logged = False
