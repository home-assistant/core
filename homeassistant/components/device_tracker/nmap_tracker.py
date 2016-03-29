"""
Support for scanning a network with nmap.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.nmap_scanner/
"""
import logging
import re
import subprocess
from collections import namedtuple
from datetime import timedelta

import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import CONF_HOSTS
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle, convert

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

# interval in minutes to exclude devices from a scan while they are home
CONF_HOME_INTERVAL = "home_interval"

REQUIREMENTS = ['python-nmap==0.6.0']


def get_scanner(hass, config):
    """Validate the configuration and return a Nmap scanner."""
    if not validate_config(config, {DOMAIN: [CONF_HOSTS]},
                           _LOGGER):
        return None

    scanner = NmapDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None

Device = namedtuple("Device", ["mac", "name", "ip", "last_update"])


def _arp(ip_address):
    """Get the MAC address for a given IP."""
    cmd = ['arp', '-n', ip_address]
    arp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = arp.communicate()
    match = re.search(r'(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})', str(out))
    if match:
        return match.group(0)
    _LOGGER.info("No MAC address found for %s", ip_address)
    return None


class NmapDeviceScanner(object):
    """This class scans for devices using nmap."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = []

        self.hosts = config[CONF_HOSTS]
        minutes = convert(config.get(CONF_HOME_INTERVAL), int, 0)
        self.home_interval = timedelta(minutes=minutes)

        self.success_init = self._update_info()
        _LOGGER.info("nmap scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""
        filter_named = [device.name for device in self.last_results
                        if device.mac == mac]

        if filter_named:
            return filter_named[0]
        else:
            return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Scan the network for devices.

        Returns boolean if scanning successful.
        """
        _LOGGER.info("Scanning")

        from nmap import PortScanner, PortScannerError
        scanner = PortScanner()

        options = "-F --host-timeout 5s"

        if self.home_interval:
            boundary = dt_util.now() - self.home_interval
            last_results = [device for device in self.last_results
                            if device.last_update > boundary]
            if last_results:
                # Pylint is confused here.
                # pylint: disable=no-member
                options += " --exclude {}".format(",".join(device.ip for device
                                                           in last_results))
        else:
            last_results = []

        try:
            result = scanner.scan(hosts=self.hosts, arguments=options)
        except PortScannerError:
            return False

        now = dt_util.now()
        for ipv4, info in result['scan'].items():
            if info['status']['state'] != 'up':
                continue
            name = info['hostnames'][0]['name'] if info['hostnames'] else ipv4
            # Mac address only returned if nmap ran as root
            mac = info['addresses'].get('mac') or _arp(ipv4)
            if mac is None:
                continue
            last_results.append(Device(mac.upper(), name, ipv4, now))

        self.last_results = last_results

        _LOGGER.info("nmap scan successful")
        return True
