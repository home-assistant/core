"""
homeassistant.components.device_tracker.fritz
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unfortunately, you have to execute the following command by hand:
sudo apt-get install libxslt-dev libxml2-dev

Device tracker platform that supports scanning a FitzBox router for device
presence.

Configuration:

To use the fritz tracker you have to adapt your configuration.yaml by
using the following template:

device_tracker:
  platform: fritz
  host: YOUR_ROUTER_IP
  username: YOUR_ADMIN_USERNAME
  password: YOUR_ADMIN_PASSWORD


Description:

host
*Optional
The IP address of your router, e.g. 192.168.0.1.
It is optional since every fritzbox is also reachable by using
the 169.254.1.1 IP.

username
*Optional
The username of an user with administrative privileges, usually 'admin'.
However, it seems that it is not necessary to use it in
current generation fritzbox routers because the necessary data
can be retrieved anonymously.

password
*Optional
The password for your given admin account.
However, it seems that it is not necessary to use it in current
generation fritzbox routers because the necessary data can
be retrieved anonymously.
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
    """
    Validates config and returns FritzBoxScanner
    @param hass:
    @param config:
    @return:
    """
    if not validate_config(config,
                           {DOMAIN: []},
                           _LOGGER):
        return None
    scanner = FritzBoxScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


# pylint: disable=too-many-instance-attributes
class FritzBoxScanner(object):
    """
    This class queries a FritzBox router. It is using the
    fritzconnection library for communication with the router.

    The API description can be found under:
    https://pypi.python.org/pypi/fritzconnection/0.4.6

    This scanner retrieves the list of known hosts and checks
    their corresponding states (on, or off).

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

        # Establish a connection to the fritzbox
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
            _LOGGER.error("Failed to establish connection to FritzBox "
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
        """
        Retrieves latest information from the FritzBox.
        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Scanning")
        self.last_results = self.fritz_box.get_hosts_info()
        return True
