"""The Gree Climate integration."""
import asyncio
import logging

from greeclimate.device import (
    Device,
    DeviceInfo,
    DeviceNotBoundError,
    DeviceTimeoutError,
)
from greeclimate.discovery import Discovery
from pizone.discovery import DISCOVERY_TIMEOUT

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .bridge import DeviceDataUpdateCoordinator
from .const import COORDINATORS, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Gree Climate component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Gree Climate from a config entry."""

    async def async_device_found(device_info: DeviceInfo):
        """Initialize and bind discovered devices."""
        device = Device(device_info)
        try:
            await device.bind()
        except DeviceNotBoundError:
            _LOGGER.error("Unable to bind to gree device: %s", device_info)
        except DeviceTimeoutError:
            _LOGGER.error("Timeout trying to bind to gree device: %s", device_info)
        else:
            _LOGGER.info(
                "Adding Gree device at %s:%i (%s)",
                device.device_info.ip,
                device.device_info.port,
                device.device_info.name,
            )
            coordo = DeviceDataUpdateCoordinator(hass, device)
            await coordo.async_refresh()
            return coordo

    # First we'll grab as many devices as we can find on the network
    # it's necessary to bind static devices anyway
    _LOGGER.debug("Scanning network for Gree devices")

    gree_discovery = Discovery(DISCOVERY_TIMEOUT)
    _, tasks = await gree_discovery.search_devices(async_callback=async_device_found)

    coordinators = await asyncio.gather(*tasks)
    hass.data[DOMAIN][COORDINATORS] = [x for x in coordinators if x is not None]

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, CLIMATE_DOMAIN)
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SWITCH_DOMAIN)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    results = asyncio.gather(
        hass.config_entries.async_forward_entry_unload(entry, CLIMATE_DOMAIN),
        hass.config_entries.async_forward_entry_unload(entry, SWITCH_DOMAIN),
    )

    unload_ok = False not in await results
    if unload_ok:
        hass.data[DOMAIN].pop(COORDINATORS, None)

    return unload_ok


class GreeScanner:
    """Scan and initialize Gree devices."""

    _scanner = None

    @classmethod
    @callback
    def async_get(cls, hass: HomeAssistant):
        """Get the scanner instance."""
        if cls._scanner is None:
            cls._scanner = cls(hass)
        return cls._scanner

    def __init__(self, hass: HomeAssistant):
        """Initialize class."""
        self._hass = hass

    async def _async_scan(self):
        pass
