""" Supports scanning a unifi router. """
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

CONF_PORT = "port"
CONF_VERSION = "version"
CONF_SITEID = "siteid"


def get_scanner(hass, config):
    """ Validates config and returns a unifi scanner. """
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PORT, CONF_VERSION, CONF_SITEID]},
                           _LOGGER):
        return None

    info = config[DOMAIN]

    scanner = unifiDeviceScanner(
        info[CONF_HOST], info[CONF_USERNAME], info[CONF_PASSWORD], info[CONF_PORT], info[CONF_VERSION], info[CONF_SITEID])

    return scanner if scanner.success_init else None


class unifiDeviceScanner(object):
    """ This class queries a Unifi controller server. """

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

        # The example format to initialize the controller - taken from unifi-ls-clients
        # c = Controller(args.controller, args.username, args.password, args.port, args.version, args.siteid)
        self._api = Controller(host, username, password, port, version, siteid)


        self.lock = threading.Lock()

        _LOGGER.info("Unifi object created, running first device scan.")

        self.success_init = True
        self._update_info()


    def scan_devices(self):
        """ Scans for new devices and return a
            list containing found device ids. """
        self._update_info()

        return (client['mac'] for client in self.last_results)

    def get_device_name(self, mac):
        """ Returns the name of the given device or None if we don't know. """

        for x in self.last_results:
            if (x["mac"].upper() == mac.upper()):
                try:
                    return (x["name"])
                except:
                    return (x["hostname"])



        return None


    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """ Retrieves latest information from the Unifi AP.
            Returns boolean if scanning successful. """
        if not self.success_init:
            return

        with self.lock:
            _LOGGER.info("Scanning")

            self.last_results = self._api.get_clients() or []
