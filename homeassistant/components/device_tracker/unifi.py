""" Supports scanning a unifi controller. """
import logging
from datetime import timedelta
import threading

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['unifi==1.2.3']

CONF_PORT = "port"
CONF_VERSION = "version"
CONF_SITEID = "siteid"


def get_scanner(hass, config):
    """ Returns a unifi scanner. """

    info = config[DOMAIN]

    host = info.get(CONF_HOST)
    username = info.get(CONF_USERNAME)
    password = info.get(CONF_PASSWORD)
    port = info.get(CONF_PORT)
    version = info.get(CONF_VERSION)
    siteid = info.get(CONF_SITEID)

    scanner = UnifiDeviceScanner(host, username, password,
                                 port, version, siteid)

    return scanner if scanner.success_init else None


class UnifiDeviceScanner(object):
    """ This class queries a unifi wireless access controller. """
    # pylint: disable=too-many-arguments
    def __init__(self, host, username, password, port, version, siteid):
        self.last_results = []

        try:
            # Pylint does not play nice if not every folders has an __init__.py
            # pylint: disable=no-name-in-module, import-error
            from unifi.controller import Controller
        except ImportError:
            _LOGGER.exception(
                ("Failed to import unifi. "))

            self.success_init = False

            return

        self._api = Controller(host, username, password, port, version, siteid)

        self.lock = threading.Lock()

        _LOGGER.info("Unifi object created, running first device scan.")

        # self.success_init = self._api.login()
        self.success_init = True
        # if self.success_init:
        self._update_info()
        # else:
        #    _LOGGER.error("Failed to Login")

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """
        self._update_info()

        return (client['mac'] for client in self.last_results)

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if we don't know. """
        for maclist in self.last_results:
            if maclist["mac"].upper() == mac.upper():
                try:
                    return maclist["name"]
                except StopIteration:
                    return maclist["hostname"]

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Retrieves latest information from the Netgear router.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return

        with self.lock:
            _LOGGER.info("Scanning")

            self.last_results = self._api.get_clients() or []
