"""
Support for Mikrotik routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mikrotik/
"""
import logging
import threading
from collections import namedtuple
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, \
                                CONF_PORT
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

DEFAULT_USERNAME = 'admin'
DEFAULT_PORT = 8728

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_PASSWORD),
    PLATFORM_SCHEMA.extend({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port
    }))


_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['tikapy==0.2.1']

_LEASES_CMD = '/ip/dhcp-server/lease/print'

_ARP_CMD = '/ip/arp/print'


def get_scanner(hass, config):
    """Validate the configuration and return an Mikrotik scanner."""
    scanner = MikrotikDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None

MikrotikResult = namedtuple('MikrotikResult', 'leases arp')


class MikrotikDeviceScanner(object):
    """This class queries a router running Mikrotik RouterOS."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.port = config[CONF_PORT]

        if not self.password:
            _LOGGER.error('No password specified')
            self.success_init = False
            return

        self.lock = threading.Lock()

        self.last_results = {}

        # Test the router is accessible.
        data = self.get_arp_data()
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [self.last_results[clientkey]['mac'] for clientkey,
                client in self.last_results.items()]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for key, client in self.last_results.items():
            if self.last_results[key]['mac'] == device:
                return self.last_results[key]['host']
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the Mikrotik router is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info('Connecting to device')
            data = self.get_arp_data()
            if not data:
                return False

            self.last_results = data
            return True

    def api_connection(self):
        """Retrieve data from mikrotik via RouterOS API."""
        from tikapy import TikapyClient

        host = TikapyClient(self.host, self.port)
        try:
            host.login(self.username, self.password)
        except:
            _LOGGER.error('Connection refused. Check if is API allowed.')
            return None

        try:

            leases_result = host.talk([_LEASES_CMD])
            arp_result = host.talk([_ARP_CMD])

            return MikrotikResult(leases_result, arp_result)
        except:
            _LOGGER.error('Unexpected response from router:')
            return None

    def get_arp_data(self):
        """Retrieve data from Mikrotik and return parsed result."""
        result = self.api_connection()

        if not result:
            return {}

        arps = {}
        for arpkey, arp in result.arp.items():

            if result.arp[arpkey].get('mac-address', None):
                hostname = result.arp[arpkey]['mac-address']
            for leasekey, lease in result.leases.items():
                if result.leases[leasekey]['mac-address'] == \
                        result.arp[arpkey]['mac-address']:
                    if result.leases[leasekey].get('host-name', None):
                        hostname = result.leases[leasekey]['host-name']
                    else:
                        hostname = ''
            arps[result.arp[arpkey]['address']] = {
                'ip': result.arp[arpkey]['address'],
                'mac': result.arp[arpkey]['mac-address'].upper(),
                'host': hostname,
                }
        return arps
