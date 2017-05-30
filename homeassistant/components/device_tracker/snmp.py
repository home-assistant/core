"""
Support for fetching WiFi associations through SNMP.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.snmp/
"""
import binascii
import logging
import threading
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pysnmp==4.3.7']

CONF_COMMUNITY = 'community'
CONF_AUTHKEY = 'authkey'
CONF_PRIVKEY = 'privkey'
CONF_BASEOID = 'baseoid'

DEFAULT_COMMUNITY = 'public'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_COMMUNITY, default=DEFAULT_COMMUNITY): cv.string,
    vol.Inclusive(CONF_AUTHKEY, 'keys'): cv.string,
    vol.Inclusive(CONF_PRIVKEY, 'keys'): cv.string,
    vol.Required(CONF_BASEOID): cv.string
})


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """Validate the configuration and return an snmp scanner."""
    scanner = SnmpScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class SnmpScanner(DeviceScanner):
    """Queries any SNMP capable Access Point for connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""
        from pysnmp.entity.rfc3413.oneliner import cmdgen
        from pysnmp.entity import config as cfg
        self.snmp = cmdgen.CommandGenerator()

        self.host = cmdgen.UdpTransportTarget((config[CONF_HOST], 161))
        if CONF_AUTHKEY not in config or CONF_PRIVKEY not in config:
            self.auth = cmdgen.CommunityData(config[CONF_COMMUNITY])
        else:
            self.auth = cmdgen.UsmUserData(
                config[CONF_COMMUNITY],
                config[CONF_AUTHKEY],
                config[CONF_PRIVKEY],
                authProtocol=cfg.usmHMACSHAAuthProtocol,
                privProtocol=cfg.usmAesCfb128Protocol
            )
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
        """Ensure the information from the device is up to date.

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
        """Fetch MAC addresses from access point via SNMP."""
        devices = []

        errindication, errstatus, errindex, restable = self.snmp.nextCmd(
            self.auth, self.host, self.baseoid)

        if errindication:
            _LOGGER.error("SNMPLIB error: %s", errindication)
            return
        # pylint: disable=no-member
        if errstatus:
            _LOGGER.error("SNMP error: %s at %s", errstatus.prettyPrint(),
                          errindex and restable[int(errindex) - 1][0] or '?')
            return

        for resrow in restable:
            for _, val in resrow:
                try:
                    mac = binascii.hexlify(val.asOctets()).decode('utf-8')
                except AttributeError:
                    continue
                _LOGGER.debug("Found MAC %s", mac)
                mac = ':'.join([mac[i:i+2] for i in range(0, len(mac), 2)])
                devices.append({'mac': mac})
        return devices
