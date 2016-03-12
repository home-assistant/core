"""
Support for fetching WiFi associations through SNMP.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.snmp/
"""
import binascii
import logging
import threading
from datetime import timedelta

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pysnmp==4.2.5']

CONF_COMMUNITY = "community"
CONF_BASEOID = "baseoid"


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """Validate the configuration and return an snmp scanner."""
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_COMMUNITY, CONF_BASEOID]},
                           _LOGGER):
        return None

    scanner = SnmpScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SnmpScanner(object):
    """Queries any SNMP capable Access Point for connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""
        from pysnmp.entity.rfc3413.oneliner import cmdgen
        self.snmp = cmdgen.CommandGenerator()

        self.host = cmdgen.UdpTransportTarget((config[CONF_HOST], 161))
        self.community = cmdgen.CommunityData(config[CONF_COMMUNITY])
        self.baseoid = cmdgen.MibVariable(config[CONF_BASEOID])

        self.lock = threading.Lock()

        self.last_results = []

        # Test the router is accessible
        data = self.get_snmp_data()
        self.success_init = data is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [client['mac'] for client in self.last_results
                if client.get('mac')]

    # Supressing no-self-use warning
    # pylint: disable=R0201
    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # We have no names
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the WAP is up to date.

        Return boolean if scanning successful.
        """
        if not self.success_init:
            return False

        with self.lock:
            data = self.get_snmp_data()
            if not data:
                return False

            self.last_results = data
            return True

    def get_snmp_data(self):
        """Fetch MAC addresses from WAP via SNMP."""
        devices = []

        errindication, errstatus, errindex, restable = self.snmp.nextCmd(
            self.community, self.host, self.baseoid)

        if errindication:
            _LOGGER.error("SNMPLIB error: %s", errindication)
            return
        if errstatus:
            _LOGGER.error('SNMP error: %s at %s', errstatus.prettyPrint(),
                          errindex and restable[-1][int(errindex)-1] or '?')
            return

        for resrow in restable:
            for _, val in resrow:
                mac = binascii.hexlify(val.asOctets()).decode('utf-8')
                _LOGGER.debug('Found mac %s', mac)
                mac = ':'.join([mac[i:i+2] for i in range(0, len(mac), 2)])
                devices.append({'mac': mac})
        return devices
