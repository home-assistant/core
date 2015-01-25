""" Supports scanning a Netgear router. """
import logging
from datetime import timedelta
import threading

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)


def get_scanner(hass, config):
    """ Validates config and returns a Netgear scanner. """
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return None

    info = config[DOMAIN]

    scanner = NetgearDeviceScanner(
        info[CONF_HOST], info[CONF_USERNAME], info[CONF_PASSWORD])

    return scanner if scanner.success_init else None


class NetgearDeviceScanner(object):
    """ This class queries a Netgear wireless router using the SOAP-api. """

    def __init__(self, host, username, password):
        self.last_results = []

        try:
            # Pylint does not play nice if not every folders has an __init__.py
            # pylint: disable=no-name-in-module, import-error
            import homeassistant.external.pynetgear.pynetgear as pynetgear
        except ImportError:
            _LOGGER.exception(
                ("Failed to import pynetgear. "
                 "Did you maybe not run `git submodule init` "
                 "and `git submodule update`?"))

            self.success_init = False

            return

        self._api = pynetgear.Netgear(host, username, password)
        self.lock = threading.Lock()

        _LOGGER.info("Logging in")

        self.success_init = self._api.login()

        if self.success_init:
            self._update_info()
        else:
            _LOGGER.error("Failed to Login")

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """
        self._update_info()

        return (device.mac for device in self.last_results)

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if we don't know. """
        try:
            return next(device.name for device in self.last_results
                        if device.mac == mac)
        except StopIteration:
            return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Retrieves latest information from the Netgear router.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return

        with self.lock:
            _LOGGER.info("Scanning")

            self.last_results = self._api.get_attached_devices() or []
