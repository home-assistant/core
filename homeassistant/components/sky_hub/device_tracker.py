"""Support for Sky Hub."""

from __future__ import annotations

import logging

from pyskyqhub.skyq_hub import SkyQHub
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend({vol.Optional(CONF_HOST): cv.string})


async def async_get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> SkyHubDeviceScanner | None:
    """Return a Sky Hub scanner if successful."""
    host = config[DOMAIN].get(CONF_HOST, "192.168.1.254")
    websession = async_get_clientsession(hass)
    hub = SkyQHub(websession, host)

    _LOGGER.debug("Initialising Sky Hub")
    await hub.async_connect()
    if hub.success_init:
        return SkyHubDeviceScanner(hub)

    return None


class SkyHubDeviceScanner(DeviceScanner):
    """Class which queries a Sky Hub router."""

    def __init__(self, hub):
        """Initialise the scanner."""
        self._hub = hub
        self.last_results = {}

    async def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        await self._async_update_info()
        return [device.mac for device in self.last_results]

    async def async_get_device_name(self, device):
        """Return the name of the given device."""
        return next(
            (result.name for result in self.last_results if result.mac == device),
            None,
        )

    async def async_get_extra_attributes(self, device):
        """Get extra attributes of a device."""
        device = next(
            (result for result in self.last_results if result.mac == device), None
        )
        if device is None:
            return {}

        return device.asdict()

    async def _async_update_info(self):
        """Ensure the information from the Sky Hub is up to date."""
        _LOGGER.debug("Scanning")

        if not (data := await self._hub.async_get_skyhub_data()):
            return

        self.last_results = data
