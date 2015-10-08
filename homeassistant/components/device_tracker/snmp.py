"""
homeassistant.components.device_tracker.snmp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports fetching WiFi assiciations
through SNMP

This device tracker needs SNMP to be enabled on the WRT or WAP

Configuration:

device_tracker:
  platform: snmp
  host: YOUR_WAP_IP
  community: SNMP_COMMUNITY
  baseoid: BASE_OID

Variables:
    Host
    *required
    The IP address of the router, e.g. 192.168.1.1

    community
    *Required
    The SNMP community. Read-only is fine

    baseoid
    *Required
    The OID at which WiFi associations can be found

    Little help with base oids:
        Microtik: 1.3.6.1.4.1.14988.1.1.1.2.1.1 (confirmed)
        Aruba: 1.3.6.1.4.1.14823.2.3.3.1.2.4.1.2 (untested)

"""
import logging
from datetime import timedelta
import threading
import binascii

from homeassistant.const import CONF_HOST
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pysnmp==4.2.5']

CONF_COMMUNITY = "community"
CONF_BASEOID = "baseoid"


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """ Validates config and returns an snmp scanner """
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_COMMUNITY, CONF_BASEOID]},
                           _LOGGER):
        return None

    scanner = SnmpScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SnmpScanner(object):
    """
    This class queries any SNMP capable Acces Point for connected devices.
    """
    def __init__(self, config):
        self.host = config[CONF_HOST]
        self.community = config[CONF_COMMUNITY]
        self.baseoid = config[CONF_BASEOID]

        self.lock = threading.Lock()

        self.last_results = []

        # Test the router is accessible
        data = self.get_snmp_data()
        self.success_init = data is not None

    def scan_devices(self):
        """
        Scans for new devices and return a list containing found device IDs.
        """

        self._update_info()
        return [client['mac'] for client in self.last_results]

    # Supressing no-self-use warning
    # pylint: disable=R0201
    def get_device_name(self, device):
        """ Returns the name of the given device or None if we don't know. """
        # We have no names
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """
        Ensures the information from the WAP is up to date.
        Returns boolean if scanning successful.
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
        """ Fetch mac addresses from WAP via SNMP. """
        from pysnmp.entity.rfc3413.oneliner import cmdgen

        devices = []

        snmp = cmdgen.CommandGenerator()
        errindication, errstatus, errindex, restable = snmp.nextCmd(
            cmdgen.CommunityData(self.community),
            cmdgen.UdpTransportTarget((self.host, 161)),
            cmdgen.MibVariable(self.baseoid)
        )

        if errindication:
            # Supressing logging-format-interpolation
            # pylint: disable=W1202
            _LOGGER.error("SNMPLIB error: {}".format(errindication))
            return
        if errstatus:
            err = "SNMP error: {} at {}"
            # Supressing logging-format-interpolation
            # pylint: disable=W1202
            _LOGGER.error(err.format(errstatus.prettyPrint(),
                                     errindex and
                                     restable[-1][int(errindex)-1]
                                     or '?'))
            return

        for resrow in restable:
            for _, val in resrow:
                mac = binascii.hexlify(val.asOctets()).decode('utf-8')
                mac = ':'.join([mac[i:i+2] for i in range(0, len(mac), 2)])
                devices.append({'mac': mac})
        return devices
