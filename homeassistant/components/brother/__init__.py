"""The Brother component."""
import asyncio
from datetime import timedelta
import logging

from brother import Brother, SnmpError, UnsupportedModel

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TYPE
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import Throttle

from .const import DOMAIN

PLATFORMS = ["sensor"]

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Config):
    """Set up the Brother component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Brother from a config entry."""
    host = entry.data[CONF_HOST]
    kind = entry.data[CONF_TYPE]

    brother = BrotherPrinterData(host, kind)

    await brother.async_update()

    if not brother.available:
        raise ConfigEntryNotReady()

    hass.data[DOMAIN][entry.entry_id] = brother

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class BrotherPrinterData:
    """Define an object to hold sensor data."""

    def __init__(self, host, kind):
        """Initialize."""
        self._brother = Brother(host, kind=kind)
        self.host = host
        self.model = None
        self.serial = None
        self.firmware = None
        self.available = False
        self.data = {}
        self.unavailable_logged = False

    @Throttle(DEFAULT_SCAN_INTERVAL)
    async def async_update(self):
        """Update data via library."""
        try:
            await self._brother.async_update()
        except (ConnectionError, SnmpError, UnsupportedModel) as error:
            if not self.unavailable_logged:
                _LOGGER.error(
                    "Could not fetch data from %s, error: %s", self.host, error
                )
                self.unavailable_logged = True
            self.available = self._brother.available
            return

        self.model = self._brother.model
        self.serial = self._brother.serial
        self.firmware = self._brother.firmware
        self.available = self._brother.available
        self.data = self._brother.data
        if self.available and self.unavailable_logged:
            _LOGGER.info("Printer %s is available again", self.host)
            self.unavailable_logged = False
