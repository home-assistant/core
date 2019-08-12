"""Support for scanning a network with nmap."""
import logging
import re
import subprocess
from collections import namedtuple
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOSTS

_LOGGER = logging.getLogger(__name__)

CONF_EXCLUDE = 'exclude'
# Interval in minutes to exclude devices from a scan while they are home
CONF_HOME_INTERVAL = 'home_interval'
CONF_OPTIONS = 'scan_options'
DEFAULT_OPTIONS = '-F --host-timeout 5s'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOSTS): cv.ensure_list,
    vol.Required(CONF_HOME_INTERVAL, default=0): cv.positive_int,
    vol.Optional(CONF_EXCLUDE, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_OPTIONS, default=DEFAULT_OPTIONS):
        cv.string
})


def get_scanner(hass, config):
    """Validate the configuration and return a Nmap scanner."""
    return NmapDeviceScanner(config[DOMAIN])


Device = namedtuple('Device', ['mac', 'name', 'ip', 'last_update'])


def _arp(ip_address):
    """Get the MAC address for a given IP."""
    cmd = ['arp', '-n', ip_address]
    arp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = arp.communicate()
    match = re.search(r'(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})', str(out))
    if match:
        return ':'.join([i.zfill(2) for i in match.group(0).split(':')])
    _LOGGER.info('No MAC address found for %s', ip_address)
    return None


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

        _LOGGER.debug("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        _LOGGER.debug("Nmap last results %s", self.last_results)

        return [device.mac for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [result.name for result in self.last_results
                        if result.mac == device]

        if filter_named:
            return filter_named[0]
        return None

    def get_extra_attributes(self, device):
        """Return the IP of the given device."""
        filter_ip = next((
            result.ip for result in self.last_results
            if result.mac == device), None)
        return {'ip': filter_ip}

    def _update_info(self):
        """Scan the network for devices.

        Returns boolean if scanning successful.
        """
        _LOGGER.debug("Scanning...")

        from nmap import PortScanner, PortScannerError
        scanner = PortScanner()

        options = self._options

        if self.home_interval:
            boundary = dt_util.now() - self.home_interval
            last_results = [device for device in self.last_results
                            if device.last_update > boundary]
            if last_results:
                exclude_hosts = self.exclude + [device.ip for device
                                                in last_results]
            else:
                exclude_hosts = self.exclude
        else:
            last_results = []
            exclude_hosts = self.exclude
        if exclude_hosts:
            options += ' --exclude {}'.format(','.join(exclude_hosts))

        try:
            result = scanner.scan(hosts=' '.join(self.hosts),
                                  arguments=options)
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

        _LOGGER.debug("nmap scan successful")
        return True
