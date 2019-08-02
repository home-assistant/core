"""Support for Mikrotik routers as device tracker."""
from datetime import timedelta
import logging

from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.util import slugify
from homeassistant.const import CONF_HOST
from .const import (
    DOMAIN,
    CONF_ARP_PING,
    MIKROTIK_SERVICES,
    CAPSMAN,
    WIRELESS,
    DHCP,
    ARP,
    ATTR_DEVICE_TRACKER,
)
from . import CONF_METHOD

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return Mikrotik scanner."""
    if discovery_info is None:
        _LOGGER.warning("To use this you need to configure the 'mikrotik' component")
        return False
    host = discovery_info[CONF_HOST]
    api = hass.data[DOMAIN][host]
    method = discovery_info[CONF_METHOD]
    arp_ping = discovery_info[CONF_ARP_PING]
    scanner = MikrotikScanner(hass, api, host, method, arp_ping, async_see)
    return await scanner.async_init()


class MikrotikScanner(DeviceScanner):
    """This class queries a Mikrotik device."""

    def __init__(self, hass, api, host, method, arp_ping, async_see):
        """Initialize the scanner."""
        self.hass = hass
        self.api = api
        self.host = host
        self.method = method
        self.arp_ping = arp_ping
        self.host_name = api.get_hostname()
        self.capsman = None
        self.wireless = None
        self.arp = {}
        self.dhcp = {}
        self.device_tracker = None
        self.async_see = async_see

    async def async_init(self):
        """Further initialize connection to Mikrotik Device."""
        await self.api.update_info()
        connected = self.api.connected()
        if connected:
            self.get_method()
            await self.async_update()
            async_track_time_interval(
                self.hass, self.async_update, DEFAULT_SCAN_INTERVAL
            )
        return connected

    async def async_update(self, now=None):
        """Ensure the information from Mikrotik device is up to date."""
        await self.update_device_tracker(self.method)
        if not self.api.connected():
            return

        devices = self.device_tracker
        for mac in devices:
            await self.async_see(mac=mac, attributes=devices[mac])

    def get_method(self):
        """Determine the device tracker polling method."""
        self.capsman = self.api.get_api(MIKROTIK_SERVICES[CAPSMAN])
        if not self.capsman:
            _LOGGER.info(
                "Mikrotik %s: Not a CAPsMAN controller. Trying "
                "local wireless interfaces.",
                (self.host),
            )
        self.wireless = self.api.get_api(MIKROTIK_SERVICES[WIRELESS])

        if (not self.capsman and not self.wireless) or self.method == "ip":
            _LOGGER.info(
                "Mikrotik %s: Wireless adapters not found. Try to "
                "use DHCP lease table as presence tracker source. "
                "Please decrease lease time as much as possible",
                self.host,
            )

        if self.method:
            _LOGGER.info(
                "Mikrotik %s: Manually selected polling method %s",
                self.host,
                self.method,
            )
        else:
            if self.capsman:
                self.method = CAPSMAN
            elif self.wireless:
                self.method = WIRELESS
            else:
                self.method = DHCP

        _LOGGER.info(
            "Mikrotik %s: Using %s for device tracker.", self.host, self.method
        )

    async def update_device_tracker(self, method=None):
        """Update device_tracker from Mikrotik API."""
        self.device_tracker = {}
        if method is None:
            return
        _LOGGER.debug(
            "[%s] Updating Mikrotik device_tracker using %s.", self.host, method
        )

        data = self.api.get_api(MIKROTIK_SERVICES[method])
        if data is None:
            self.update_info()
            return

        arp = self.api.get_api(MIKROTIK_SERVICES[ARP])
        for device in arp:
            if "mac-address" in device and device["invalid"] is False:
                mac = device["mac-address"]
                self.arp[mac] = device

        for device in data:
            mac = device["mac-address"]
            if method == DHCP:
                if "active-address" not in device:
                    continue
                self.dhcp[mac] = data
                if self.arp_ping and mac in arp:
                    interface = arp[mac]["interface"]
                    if not self.arp_ping(mac, interface):
                        continue

            attributes = {}
            for attrib in ATTR_DEVICE_TRACKER:
                if attrib in device:
                    attributes[slugify(attrib)] = device[attrib]
            attributes["source_type"] = "router"
            attributes["scanner_type"] = method
            attributes["scanner_host"] = self.host
            attributes["scanner_host_name"] = self.host_name

            if mac in self.arp:
                attributes["ip_address"] = self.arp[mac]["address"]

            if mac in self.arp:
                attributes["host_name"] = self.dhcp[mac]["host-name"]

            self.device_tracker[mac] = attributes

    def arp_ping(self, mac, interface):
        """Attempt to arp ping MAC address via interface."""
        params = {
            "arp-ping": "yes",
            "interval": "100ms",
            "count": 3,
            "interface": interface,
            "address": mac,
        }
        cmd = "/ping"
        data = self.api.api_get(cmd, params)
        status = 0
        for result in data:
            if "status" in result:
                status += 1
        if status == len(data):
            return None
        return data
