""" Supports scanning a Netgear router. """
import logging
from datetime import timedelta
import threading

import homeassistant as ha
import homeassistant.util as util
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """ Validates config and returns a Netgear scanner. """
    if not util.validate_config(config,
                                {DOMAIN: [ha.CONF_HOST, ha.CONF_USERNAME,
                                          ha.CONF_PASSWORD]},
                                _LOGGER):
        return None

    scanner = NetgearDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class NetgearDeviceScanner(object):
    """ This class queries a Netgear wireless router using the SOAP-api. """

    def __init__(self, config):
        host = config[ha.CONF_HOST]
        username, password = config[ha.CONF_USERNAME], config[ha.CONF_PASSWORD]

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
        if self._api.login():
            self.success_init = True
            self._update_info()

        else:
            _LOGGER.error("Failed to Login")

            self.success_init = False

    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """

        self._update_info()

        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if we don't know. """

        filter_named = [device.name for device in self.last_results
                        if device.mac == mac]

        if filter_named:
            return filter_named[0]
        else:
            return None

    @util.AddCooldown(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Retrieves latest information from the Netgear router.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return

        with self.lock:
            _LOGGER.info("Scanning")

            self.last_results = self._api.get_attached_devices()
