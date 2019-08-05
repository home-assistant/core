"""Support for Mikrotik routers as device tracker."""
import logging

from homeassistant.components.device_tracker import DeviceScanner, SOURCE_TYPE_ROUTER
from homeassistant.helpers.event import track_utc_time_change
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


def setup_scanner(hass, config, see, discovery_info=None):
    """Validate the configuration and return Mikrotik scanner."""
    if discovery_info is None:
        _LOGGER.warning("To use this you need to configure the 'mikrotik' component")
        return False
    host = discovery_info[CONF_HOST]
    api = hass.data[DOMAIN][host]
    method = discovery_info[CONF_METHOD]
    arp_ping = discovery_info[CONF_ARP_PING]
    MikrotikScanner(hass, api, host, method, arp_ping, see)


class MikrotikScanner(DeviceScanner):
    """This class queries a Mikrotik device."""

    def __init__(self, hass, api, host, method, arp_ping, see):
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
        self.see = see
        self.get_method()
        self._update()

        track_utc_time_change(self.hass, self._update, second=range(0, 60, 30))

    def _update(self, now=None):
        """Ensure the information from Mikrotik device is up to date."""
        self.update_device_tracker(self.method)
        if not self.api.connected():
            return

        devices = self.device_tracker
        for mac in devices:
            if "host_name" in devices[mac]:
                dev_id = slugify(devices[mac]["host_name"])
            else:
                dev_id = mac
            self.see(dev_id=dev_id, mac=mac, attributes=devices[mac])

    def get_method(self):
        """Determine the device tracker polling method."""
        self.capsman = self.api.command(MIKROTIK_SERVICES[CAPSMAN])
        if not self.capsman:
            _LOGGER.info(
                "Mikrotik %s: Not a CAPsMAN controller. "
                "Trying local wireless interfaces.",
                (self.host),
            )
        self.wireless = self.api.command(MIKROTIK_SERVICES[WIRELESS])

        if (not self.capsman and not self.wireless) or self.method == DHCP:
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

    def update_device_tracker(self, method=None):
        """Update device_tracker from Mikrotik API."""
        _LOGGER.debug(
            "[%s] Updating Mikrotik device_tracker using %s.", self.host, method
        )
        self.device_tracker = {}
        data = self.api.command(MIKROTIK_SERVICES[method])
        if data is None:
            return

        arp = self.api.command(MIKROTIK_SERVICES[ARP])
        for device in arp:
            if "mac-address" in device and device["invalid"] is False:
                mac = device["mac-address"]
                self.arp[mac] = device

        for device in data:
            if method == DHCP:
                if "active-address" not in device:
                    continue
                self.dhcp[mac] = device
                if self.arp_ping:
                    if mac not in self.arp:
                        continue
                    interface = self.arp[mac]["interface"]
                    if not self.do_arp_ping(mac, interface):
                        continue

            mac = device["mac-address"]
            attrs = {}

            if mac in self.dhcp and "host-name" in self.dhcp[mac]:
                attrs["host_name"] = self.dhcp[mac]["host-name"]

            if mac in self.arp:
                attrs["ip_address"] = self.arp[mac]["address"]

            for attr in ATTR_DEVICE_TRACKER:
                if attr in device:
                    attrs[slugify(attr)] = device[attr]

            attrs["source_type"] = SOURCE_TYPE_ROUTER
            attrs["scanner_type"] = method
            attrs["scanner_host"] = self.host
            attrs["scanner_host_name"] = self.host_name
            self.device_tracker[mac] = attrs

    def do_arp_ping(self, mac, interface):
        """Attempt to arp ping MAC address via interface."""
        params = {
            "arp-ping": "yes",
            "interval": "100ms",
            "count": 3,
            "interface": interface,
            "address": mac,
        }
        cmd = "/ping"
        data = self.api.command(cmd, params)
        status = 0
        for result in data:
            if "status" in result:
                _LOGGER.debug(
                    "Mikrotik %s arp_ping error: %s", self.host, result["status"]
                )
                status += 1
        if status == len(data):
            return None
        return data
