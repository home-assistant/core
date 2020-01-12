"""Support for Mikrotik routers as device tracker."""
import logging

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER,
    DeviceScanner,
)
from homeassistant.const import CONF_METHOD
from homeassistant.util import slugify

from .const import (
    ARP,
    ATTR_DEVICE_TRACKER,
    CAPSMAN,
    CONF_ARP_PING,
    DHCP,
    HOSTS,
    MIKROTIK,
    MIKROTIK_SERVICES,
    WIRELESS,
)

_LOGGER = logging.getLogger(__name__)


def get_scanner(hass, config):
    """Validate the configuration and return MikrotikScanner."""
    for host in hass.data[MIKROTIK][HOSTS]:
        if DEVICE_TRACKER not in hass.data[MIKROTIK][HOSTS][host]:
            continue
        hass.data[MIKROTIK][HOSTS][host].pop(DEVICE_TRACKER, None)
        api = hass.data[MIKROTIK][HOSTS][host]["api"]
        config = hass.data[MIKROTIK][HOSTS][host]["config"]
        hostname = api.get_hostname()
        scanner = MikrotikScanner(api, host, hostname, config)
    return scanner if scanner.success_init else None


class MikrotikScanner(DeviceScanner):
    """This class queries a Mikrotik device."""

    def __init__(self, api, host, hostname, config):
        """Initialize the scanner."""
        self.api = api
        self.config = config
        self.host = host
        self.hostname = hostname
        self.method = config.get(CONF_METHOD)
        self.arp_ping = config.get(CONF_ARP_PING)
        self.dhcp = None
        self.devices_arp = {}
        self.devices_dhcp = {}
        self.device_tracker = None
        self.success_init = self.api.connected()

    def get_extra_attributes(self, device):
        """
        Get extra attributes of a device.

        Some known extra attributes that may be returned in the device tuple
        include MAC address (mac), network device (dev), IP address
        (ip), reachable status (reachable), associated router
        (host), hostname if known (hostname) among others.
        """
        return self.device_tracker.get(device) or {}

    def get_device_name(self, device):
        """Get name for a device."""
        host = self.device_tracker.get(device, {})
        return host.get("host_name")

    def scan_devices(self):
        """Scan for new devices and return a list with found device MACs."""
        self.update_device_tracker()
        return list(self.device_tracker)

    def get_method(self):
        """Determine the device tracker polling method."""
        if self.method:
            _LOGGER.debug(
                "Mikrotik %s: Manually selected polling method %s",
                self.host,
                self.method,
            )
            return self.method

        capsman = self.api.command(MIKROTIK_SERVICES[CAPSMAN])
        if not capsman:
            _LOGGER.debug(
                "Mikrotik %s: Not a CAPsMAN controller. "
                "Trying local wireless interfaces",
                (self.host),
            )
        else:
            return CAPSMAN

        wireless = self.api.command(MIKROTIK_SERVICES[WIRELESS])
        if not wireless:
            _LOGGER.info(
                "Mikrotik %s: Wireless adapters not found. Try to "
                "use DHCP lease table as presence tracker source. "
                "Please decrease lease time as much as possible",
                self.host,
            )
            return DHCP

        return WIRELESS

    def update_device_tracker(self):
        """Update device_tracker from Mikrotik API."""
        self.device_tracker = {}
        if not self.method:
            self.method = self.get_method()

        data = self.api.command(MIKROTIK_SERVICES[self.method])
        if data is None:
            return

        if self.method != DHCP:
            dhcp = self.api.command(MIKROTIK_SERVICES[DHCP])
            if dhcp is not None:
                self.devices_dhcp = load_mac(dhcp)

        arp = self.api.command(MIKROTIK_SERVICES[ARP])
        self.devices_arp = load_mac(arp)

        for device in data:
            mac = device.get("mac-address")
            if self.method == DHCP:
                if "active-address" not in device:
                    continue

                if self.arp_ping and self.devices_arp:
                    if mac not in self.devices_arp:
                        continue
                    ip_address = self.devices_arp[mac]["address"]
                    interface = self.devices_arp[mac]["interface"]
                    if not self.do_arp_ping(ip_address, interface):
                        continue

            attrs = {}
            if mac in self.devices_dhcp and "host-name" in self.devices_dhcp[mac]:
                hostname = self.devices_dhcp[mac].get("host-name")
                if hostname:
                    attrs["host_name"] = hostname

            if self.devices_arp and mac in self.devices_arp:
                attrs["ip_address"] = self.devices_arp[mac].get("address")

            for attr in ATTR_DEVICE_TRACKER:
                if attr in device and device[attr] is not None:
                    attrs[slugify(attr)] = device[attr]
            attrs["scanner_type"] = self.method
            attrs["scanner_host"] = self.host
            attrs["scanner_hostname"] = self.hostname
            self.device_tracker[mac] = attrs

    def do_arp_ping(self, ip_address, interface):
        """Attempt to arp ping MAC address via interface."""
        params = {
            "arp-ping": "yes",
            "interval": "100ms",
            "count": 3,
            "interface": interface,
            "address": ip_address,
        }
        cmd = "/ping"
        data = self.api.command(cmd, params)
        if data is not None:
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


def load_mac(devices=None):
    """Load dictionary using MAC address as key."""
    if not devices:
        return None
    mac_devices = {}
    for device in devices:
        if "mac-address" in device:
            mac = device.pop("mac-address")
            mac_devices[mac] = device
    return mac_devices
