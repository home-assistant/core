"""
homeassistant.components.device_tracker.fritz
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports scanning a FRITZ!Box router for device
presence.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.fritz/
"""
import logging
from datetime import timedelta

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def get_scanner(hass, config):
    """ Validates config and returns FritzBoxScanner. """
    if not validate_config(config,
                           {DOMAIN: []},
                           _LOGGER):
        return None

    scanner = FritzBoxScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


# pylint: disable=too-many-instance-attributes
class FritzBoxScanner(object):
    """
    This class queries a FRITZ!Box router. It is using the
    fritzconnection library for communication with the router.

    The API description can be found under:
    https://pypi.python.org/pypi/fritzconnection/0.4.6

    This scanner retrieves the list of known hosts and checks their
    corresponding states (on, or off).

    Due to a bug of the fritzbox api (router side) it is not possible
    to track more than 16 hosts.
    """
    def __init__(self, config):
        self.last_results = []
        self.host = '169.254.1.1'  # This IP is valid for all fritzboxes
        self.username = 'admin'
        self.password = ''
        self.success_init = True

        # Try to import the fritzconnection library
        try:
            # noinspection PyPackageRequirements,PyUnresolvedReferences
            import fritzconnection as fc
        except ImportError:
            _LOGGER.exception("""Failed to import Python library
                                fritzconnection. Please run
                                <home-assistant>/setup to install it.""")
            self.success_init = False
            return

        # Check for user specific configuration
        if CONF_HOST in config.keys():
            self.host = config[CONF_HOST]
        if CONF_USERNAME in config.keys():
            self.username = config[CONF_USERNAME]
        if CONF_PASSWORD in config.keys():
            self.password = config[CONF_PASSWORD]

        # Establish a connection to the FRITZ!Box
        try:
            self.fritz_box = fc.FritzHosts(address=self.host,
                                           user=self.username,
                                           password=self.password)
        except (ValueError, TypeError):
            self.fritz_box = None

        # At this point it is difficult to tell if a connection is established.
        # So just check for null objects ...
        if self.fritz_box is None or not self.fritz_box.modelname:
            self.success_init = False

        if self.success_init:
            _LOGGER.info("Successfully connected to %s",
                         self.fritz_box.modelname)
            self._update_info()
        else:
            _LOGGER.error("Failed to establish connection to FRITZ!Box "
                          "with IP: %s", self.host)

    def scan_devices(self):
        """ Scan for new devices and return a list of found device ids. """
        self._update_info()
        active_hosts = []
        for known_host in self.last_results:
            if known_host["status"] == "1":
                active_hosts.append(known_host["mac"])
        return active_hosts

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if is not known. """
        ret = self.fritz_box.get_specific_host_entry(mac)["NewHostName"]
        if ret == {}:
            return None
        return ret

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Retrieves latest information from the FRITZ!Box. """
        if not self.success_init:
            return False

        _LOGGER.info("Scanning")
        self.last_results = self.fritz_box.get_hosts_info()
        return True
