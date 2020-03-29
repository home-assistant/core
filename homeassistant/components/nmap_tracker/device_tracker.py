"""Support for scanning a network with nmap."""
from collections import namedtuple
from datetime import timedelta
import logging
import re

from getmac import get_mac_address
from nmap import PortScanner, PortScannerError
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOSTS
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_EXCLUDE = "exclude"
# Interval in minutes to exclude devices from a scan while they are home
CONF_HOME_INTERVAL = "home_interval"
CONF_OPTIONS = "scan_options"
DEFAULT_OPTIONS = "-F --host-timeout 5s"
CONF_ARP_FILE = "arp_file"
DEFAULT_ARP_FILE = "/host/arp"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOSTS): cv.ensure_list,
        vol.Required(CONF_HOME_INTERVAL, default=0): cv.positive_int,
        vol.Optional(CONF_EXCLUDE, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_OPTIONS, default=DEFAULT_OPTIONS): cv.string,
        vol.Optional(CONF_ARP_FILE, default=DEFAULT_ARP_FILE): cv.string,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return a Nmap scanner."""
    return NmapDeviceScanner(config[DOMAIN])


Device = namedtuple("Device", ["mac", "name", "ip", "last_update"])

MAC_RE_COLON = r"([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})"


class NmapDeviceScanner(DeviceScanner):
    """This class scans for devices using nmap."""

    exclude = []

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []

        self.hosts = config[CONF_HOSTS]
        self.exclude = config[CONF_EXCLUDE]
        minutes = config[CONF_HOME_INTERVAL]
        self._options = config[CONF_OPTIONS]
        self.home_interval = timedelta(minutes=minutes)
        self._arp_file = config[CONF_ARP_FILE]

        _LOGGER.debug("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        _LOGGER.debug("Nmap last results %s", self.last_results)

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [
            result.name for result in self.last_results if result.mac == device
        ]

        if filter_named:
            return filter_named[0]
        return None

    def get_extra_attributes(self, device):
        """Return the IP of the given device."""
        filter_ip = next(
            (result.ip for result in self.last_results if result.mac == device), None
        )
        return {"ip": filter_ip}

    def _search(self, regex, text, group_index=0):
        match = re.search(regex, text)
        if match:
            return match.groups()[group_index]
        return None

    def _read_file(self, filepath):
        """Return content of given file."""
        try:
            with open(filepath) as f:
                return f.read()
        except (OSError, IOError):  # This is IOError on Python 2.7
            _LOGGER.debug("Could not find file: '%s'", filepath)
            return None

    def _read_arp_file(self, host):
        """Return the MAC for given IP."""
        data = self._read_file(self._arp_file)
        if data is not None and len(data) > 1:
            # Need a space, otherwise a search for 192.168.16.2
            # will match 192.168.16.254 if it comes first!
            return self._search(re.escape(host) + r" .+" + MAC_RE_COLON, data)
        return None

    def _update_info(self):
        """Scan the network for devices.

        Returns boolean if scanning successful.
        """
        _LOGGER.debug("Scanning...")

        scanner = PortScanner()

        options = self._options

        if self.home_interval:
            boundary = dt_util.now() - self.home_interval
            last_results = [
                device for device in self.last_results if device.last_update > boundary
            ]
            if last_results:
                exclude_hosts = self.exclude + [device.ip for device in last_results]
            else:
                exclude_hosts = self.exclude
        else:
            last_results = []
            exclude_hosts = self.exclude
        if exclude_hosts:
            options += " --exclude {}".format(",".join(exclude_hosts))

        try:
            result = scanner.scan(hosts=" ".join(self.hosts), arguments=options)
        except PortScannerError:
            return False

        now = dt_util.now()
        for ipv4, info in result["scan"].items():
            if info["status"]["state"] != "up":
                continue
            name = info["hostnames"][0]["name"] if info["hostnames"] else ipv4
            # Mac address only returned if nmap ran as root
            mac = (
                info["addresses"].get("mac")
                or get_mac_address(ip=ipv4)
                or self._read_arp_file(ipv4)
            )
            if mac is None:
                _LOGGER.info("No MAC address found for %s", ipv4)
                continue
            last_results.append(Device(mac.upper(), name, ipv4, now))

        self.last_results = last_results

        _LOGGER.debug("nmap scan successful")
        return True
