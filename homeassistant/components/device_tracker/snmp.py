"""
homeassistant.components.device_tracker.demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fetch wifi associations through snmp

device_tracker:
  platform: snmp
  host: YOUR_WAP_IP
  community: SNMP_COMMUNITY
  baseoid: BASE_OID


Little help with base oids:
    Microtik: 1.3.6.1.4.1.14988.1.1.1.2.1.1 (confirmed)
    Aruba: 1.3.6.1.4.1.14823.2.3.3.1.2.4.1.2 (untested)

"""
import logging
from datetime import timedelta
import threading
import binascii

from homeassistant.const import CONF_HOST, CONF_COMMUNITY, CONF_BASEOID
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pysnmp']

def setup_scanner(hass, config):
    """ Setup snmp scanning """
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_COMMUNITY, CONF_BASEOID]},
                           _LOGGER):
        return None

    scanner = SnmpScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SnmpScanner(object):
    """ This class queries any SNMP capable Acces Point for connected devices. """
    def __init__(self, config):
        self.host = config[CONF_HOST]
        self.community = config[CONF_USERNAME]
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
        return self.last_results

    def get_device_name(self, device):
        """ Returns the name of the given device or None if we don't know. """
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
        devices = []


        from pysnmp.entity.rfc3413.oneliner import cmdgen

        oid='1.3.6.1.4.1.14988.1.1.1.2.1.1'
        cmdGen = cmdgen.CommandGenerator()

        errorIndication, errorStatus, errorIndex, varBindTable = cmdGen.nextCmd(
            cmdgen.CommunityData( self.community ),
            cmdgen.UdpTransportTarget( ( self.host , 161) ),
            cmdgen.MibVariable( self.baseoid )
        )

        if errorIndication:
            _LOGGER.exception( "SNMPLIB error: {}".format( errorIndication ) )
            return
        else:
            if errorStatus:
                _LOGGER.exception( "SNMP error: {} at {}".format( errorStatus.prettyPrint(), errorIndex and varBindTable[-1][int(errorIndex)-1] or '?' ) )
                return
            else:
                for varBindTableRow in varBindTable:
                    for val in varBindTableRow.values():
                        devices.append( convertMac( val ) )
        return devices

    def convertMac(octect):
        ''' Convert a binary mac address to a string '''
        mac = []
        for x in list(octet):
            mac.append(binascii.b2a_hex(x))
        return ":".join(mac)

