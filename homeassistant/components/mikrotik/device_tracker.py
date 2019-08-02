"""Support for Mikrotik routers as device tracker."""
from datetime import timedelta
import logging

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.device_tracker import (
    DeviceScanner, DOMAIN as DEVICE_TRACKER)
from homeassistant.const import CONF_HOST
from .const import (DOMAIN, CLIENT, MIKROTIK_SERVICES,
                    CAPSMAN, WIRELESS, DHCP)
from . import CONF_METHOD

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return Mikrotik scanner."""
    if discovery_info is None:
        _LOGGER.warning(
            "To use this you need to configure the 'mikrotik' component")
        return False
    host = discovery_info[CONF_HOST]
    client = hass.data[CLIENT][host]
    method = discovery_info[CONF_METHOD]
    scanner = MikrotikScanner(hass, client, host, method, async_see)
    return await scanner.async_init()


class MikrotikScanner(DeviceScanner):
    """This class queries a Mikrotik device."""

    def __init__(self, hass, client, host, method, async_see):
        """Initialize the scanner."""
        self.hass = hass
        self.client = client
        self.api = client.api
        self.host = host
        self.method = method
        self.async_see = async_see

    async def async_init(self):
        """Further initialize connection to Mikrotik Device."""
        await self.api.update_info()
        connected = self.api.connected()
        if connected:
            self.get_method()
            await self.async_update()
            async_track_time_interval(self.hass,
                                      self.async_update,
                                      DEFAULT_SCAN_INTERVAL)
        return connected

    async def async_update(self, now=None):
        """Ensure the information from Mikrotik device is up to date."""
        await self.api.update_device_tracker(self.method)
        if not self.api.connected():
            return
        data = self.hass.data[DOMAIN][self.host]
        devices = data.get(DEVICE_TRACKER)
        for mac in devices:
            await self.async_see(mac=mac, attributes=devices[mac])

    def get_method(self):
        """Determine the device tracker polling method."""
        capsman = self.api.get_api(MIKROTIK_SERVICES[CAPSMAN])
        if not capsman:
            _LOGGER.info("Mikrotik %s: Not a CAPsMAN controller. Trying "
                         "local wireless interfaces.", (self.host))
        else:
            self.method = CAPSMAN

        wireless = self.api.get_api(MIKROTIK_SERVICES[WIRELESS])
        if not wireless:
            _LOGGER.info("Mikrotik %s: No wireless interfaces. "
                         "Trying DHCP leases.", (self.host))
        else:
            self.method = WIRELESS

        if (not capsman and not wireless) or self.method == 'ip':
            _LOGGER.info(
                "Mikrotik %s: Wireless adapters not found. Try to "
                "use DHCP lease table as presence tracker source. "
                "Please decrease lease time as much as possible",
                self.host)

        if self.method:
            _LOGGER.info("Mikrotik %s: Manually selected polling method %s",
                         self.host, self.method)
        else:
            self.method = DHCP

        _LOGGER.info(
            "Mikrotik %s: Using %s for device tracker.",
            self.host, self.method)
