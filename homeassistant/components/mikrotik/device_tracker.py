"""Support for Mikrotik routers as device tracker."""
from datetime import timedelta
import logging

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.const import CONF_HOST
from . import CLIENT, DOMAIN as MIKROTIK_DOMAIN, DEVICE_TRACKER


_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return Mikrotik scanner."""
    if discovery_info is None:
        _LOGGER.warning(
            "To use this you need to configure the 'mikrotik' component")
        return False
    scanner = MikrotikScanner(hass, hass.data[CLIENT],
                              discovery_info, async_see)
    return await scanner.async_init()


class MikrotikScanner(DeviceScanner):
    """This class queries a Mikrotik device."""

    def __init__(self, hass, client, config, async_see):
        """Initialize the scanner."""
        self.async_see = async_see
        self.hass = hass
        self.client = client
        self.host = config[CONF_HOST]

    async def async_init(self):
        """Further initialize connection to Mikrotik Device."""
        await self.client.update_info(self.host)
        data = self.hass.data[MIKROTIK_DOMAIN][self.host]
        info = data.get('info', None)
        connected = bool(info)
        if connected:
            await self.async_update()
            async_track_time_interval(self.hass,
                                      self.async_update,
                                      DEFAULT_SCAN_INTERVAL)
        return connected

    async def async_update(self, now=None):
        """Ensure the information from Mikrotik device is up to date."""
        await self.client.update_device_tracker(self.host)
        data = self.hass.data[MIKROTIK_DOMAIN][self.host]
        devices = data.get(DEVICE_TRACKER)
        for mac in devices:
            await self.async_see(mac=mac, attributes=devices[mac])
