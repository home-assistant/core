""" Supports scanning using nmap. """
import logging
from datetime import timedelta
import threading
from collections import namedtuple
import subprocess
import re

from libnmap.process import NmapProcess
from libnmap.parser import NmapParser, NmapParserException

from homeassistant.const import CONF_HOSTS
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """ Validates config and returns a Nmap scanner. """
    if not validate_config(config, {DOMAIN: [CONF_HOSTS]},
                           _LOGGER):
        return None

    scanner = NmapDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None

Device = namedtuple("Device", ["mac", "name"])


def _arp(ip_address):
    """ Get the MAC address for a given IP """
    cmd = ['arp', '-n', ip_address]
    arp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = arp.communicate()
    match = re.search('(([0-9A-Fa-f]{2}\\:){5}[0-9A-Fa-f]{2})', str(out))
    if match:
        return match.group(0)
    _LOGGER.info("No MAC address found for %s", ip_address)
    return ''


class NmapDeviceScanner(object):
    """ This class scans for devices using nmap """

    def __init__(self, config):
        self.last_results = []

        self.lock = threading.Lock()
        self.hosts = config[CONF_HOSTS]

        self.success_init = True
        self._update_info()
        _LOGGER.info("nmap scanner initialized")

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """

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
        """ Scans the network for devices.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info("Scanning")

            nmap = NmapProcess(targets=self.hosts, options="-F")

            nmap.run()

            if nmap.rc == 0:
                try:
                    results = NmapParser.parse(nmap.stdout)
                    self.last_results = []
                    for host in results.hosts:
                        if host.is_up():
                            if host.hostnames:
                                name = host.hostnames[0]
                            else:
                                name = host.ipv4
                            if host.mac:
                                mac = host.mac
                            else:
                                mac = _arp(host.ipv4)
                            if mac:
                                device = Device(mac, name)
                                self.last_results.append(device)
                    _LOGGER.info("nmap scan successful")
                    return True
                except NmapParserException as parse_exc:
                    _LOGGER.error("failed to parse nmap results: %s",
                                  parse_exc.msg)
                    self.last_results = []
                    return False

            else:
                self.last_results = []
                _LOGGER.error(nmap.stderr)
                return False
