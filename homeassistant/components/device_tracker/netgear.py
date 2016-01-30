"""
homeassistant.components.device_tracker.netgear
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Device tracker platform that supports scanning a Netgear router for device
presence.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.netgear/
"""
import logging
from datetime import timedelta
import threading

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.util import Throttle
from homeassistant.components.device_tracker import DOMAIN

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['pynetgear==0.3.2']


def get_scanner(hass, config):
    """ Validates config and returns a Netgear scanner. """
    info = config[DOMAIN]
    host = info.get(CONF_HOST)
    username = info.get(CONF_USERNAME)
    password = info.get(CONF_PASSWORD)

    if password is not None and host is None:
        _LOGGER.warning('Found username or password but no host')
        return None

    scanner = NetgearDeviceScanner(host, username, password)

    return scanner if scanner.success_init else None


class NetgearDeviceScanner(object):
    """ This class queries a Netgear wireless router using the SOAP-API. """

    def __init__(self, host, username, password):
        import pynetgear

        self.last_results = []
        self.lock = threading.Lock()

        if host is None:
            self._api = pynetgear.Netgear()
        elif username is None:
            self._api = pynetgear.Netgear(password, host)
        else:
            self._api = pynetgear.Netgear(password, host, username)

        _LOGGER.info("Logging in")

        results = self._api.get_attached_devices()

        self.success_init = results is not None

        if self.success_init:
            self.last_results = results
        else:
            _LOGGER.error("Failed to Login")

    def scan_devices(self):
        """
        Scans for new devices and return a list containing found device ids.
        """
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
        """
        Retrieves latest information from the Netgear router.
        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return

        with self.lock:
            _LOGGER.info("Scanning")

            self.last_results = self._api.get_attached_devices() or []
