""" Supports scanning a unifi controller. """
import logging
from datetime import timedelta
import threading

from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_VERSION,
    CONF_SITEID
)
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN


# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['unifi==1.2.3']


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

    return scanner


class UnifiDeviceScanner(object):
    """ This class queries a unifi wireless access controller. """
    # pylint: disable=too-many-arguments
    def __init__(self, host, username, password, port, version, siteid):
        self.last_results = []

        # pylint: disable=no-name-in-module, import-error
        from unifi.controller import Controller

        self._api = Controller(host, username, password, port, version, siteid)

        self.lock = threading.Lock()

        results = self._api
        if results is None:
            _LOGGER.error("Failed to Login")
            return

        _LOGGER.info("Unifi object created, running first device scan.")

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """
        self._update_info()

        return (client['mac'] for client in self.last_results)

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if we don't know. """
        for maclist in self.last_results:
            return maclist.get('name') or maclist.get('hostname')

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Retrieves latest information from the unifi WAP controller. """

        with self.lock:
            _LOGGER.info("Scanning")

            self.last_results = self._api.get_clients() or []
