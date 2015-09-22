"""
homeassistant.components.device_tracker.nmap
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports scanning a network with nmap.

Configuration:

To use the nmap tracker you will need to add something like the following
to your configuration.yaml file.

device_tracker:
  platform: nmap_tracker
  hosts: 192.168.1.1/24

Variables:

hosts
*Required
The IP addresses to scan in the network-prefix notation (192.168.1.1/24) or
the range notation (192.168.1.1-255).

home_interval
*Optional
Number of minutes it will not scan devices that it found in previous results.
This is to save battery.
"""
import logging
from datetime import timedelta
from collections import namedtuple
import subprocess
import re

import homeassistant.util.dt as dt_util
from homeassistant.const import CONF_HOSTS
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle, convert
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

# interval in minutes to exclude devices from a scan while they are home
CONF_HOME_INTERVAL = "home_interval"

REQUIREMENTS = ['python-nmap==0.4.3']


def get_scanner(hass, config):
    """ Validates config and returns a Nmap scanner. """
    if not validate_config(config, {DOMAIN: [CONF_HOSTS]},
                           _LOGGER):
        return None

    scanner = NmapDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None

Device = namedtuple("Device", ["mac", "name", "ip", "last_update"])


def _arp(ip_address):
    """ Get the MAC address for a given IP. """
    cmd = ['arp', '-n', ip_address]
    arp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = arp.communicate()
    match = re.search(r'(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})', str(out))
    if match:
        return match.group(0)
    _LOGGER.info("No MAC address found for %s", ip_address)
    return None


class NmapDeviceScanner(object):
    """ This class scans for devices using nmap. """

    def __init__(self, config):
        self.last_results = []

        self.hosts = config[CONF_HOSTS]
        minutes = convert(config.get(CONF_HOME_INTERVAL), int, 0)
        self.home_interval = timedelta(minutes=minutes)

        self.success_init = self._update_info()
        _LOGGER.info("nmap scanner initialized")

    def scan_devices(self):
        """
        Scans for new devices and return a list containing found device ids.
        """

        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if we don't know. """

        filter_named = [device.name for device in self.last_results
                        if device.mac == mac]

        if filter_named:
            return filter_named[0]
        else:
            return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """
        Scans the network for devices.
        Returns boolean if scanning successful.
        """
        _LOGGER.info("Scanning")

        from nmap import PortScanner, PortScannerError
        scanner = PortScanner()

        options = "-F --host-timeout 5"
        exclude_targets = set()
        if self.home_interval:
            now = dt_util.now()
            for host in self.last_results:
                if host.last_update + self.home_interval > now:
                    exclude_targets.add(host)
            if len(exclude_targets) > 0:
                target_list = [t.ip for t in exclude_targets]
                options += " --exclude {}".format(",".join(target_list))

        try:
            result = scanner.scan(hosts=self.hosts, arguments=options)
        except PortScannerError:
            return False

        now = dt_util.now()
        self.last_results = []
        for ipv4, info in result['scan'].items():
            if info['status']['state'] != 'up':
                continue
            name = info['hostnames'][0] if info['hostnames'] else ipv4
            # Mac address only returned if nmap ran as root
            mac = info['addresses'].get('mac') or _arp(ipv4)
            if mac is None:
                continue
            device = Device(mac.upper(), name, ipv4, now)
            self.last_results.append(device)
        self.last_results.extend(exclude_targets)

        _LOGGER.info("nmap scan successful")
        return True
