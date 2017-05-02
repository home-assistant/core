"""
Support for Mikrotik routers as device tracker.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.mikrotik/
"""
import logging
import threading
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (CONF_HOST,
                                 CONF_PASSWORD,
                                 CONF_USERNAME,
                                 CONF_PORT)
from homeassistant.util import Throttle

REQUIREMENTS = ['librouteros==1.0.2']

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

MTK_DEFAULT_API_PORT = '8728'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=MTK_DEFAULT_API_PORT): cv.port
})


def get_scanner(hass, config):
    """Validate the configuration and return MTikScanner."""
    scanner = MikrotikScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


class MikrotikScanner(DeviceScanner):
    """This class queries a Mikrotik router."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.last_results = {}

        self.host = config[CONF_HOST]
        self.port = config[CONF_PORT]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.lock = threading.Lock()

        self.connected = False
        self.success_init = False
        self.client = None

        self.success_init = self.connect_to_device()

        if self.success_init:
            _LOGGER.info("Start polling Mikrotik router...")
            self._update_info()
        else:
            _LOGGER.error("Connection to Mikrotik failed")

    def connect_to_device(self):
        """Connect to Mikrotik method."""
        # pylint: disable=import-error
        import librouteros
        try:
            self.client = librouteros.connect(
                self.host,
                self.username,
                self.password,
                port=int(self.port)
            )

            routerboard_info = self.client(cmd='/system/routerboard/getall')

            if routerboard_info:
                _LOGGER.info("Connected to Mikrotik %s with IP %s",
                             routerboard_info[0].get('model', 'Router'),
                             self.host)
                self.connected = True

        except (librouteros.exceptions.TrapError,
                librouteros.exceptions.ConnectionError) as api_error:
            _LOGGER.error("Connection error: %s", api_error)

        return self.connected

    def scan_devices(self):
        """Scan for new devices and return a list with found device MACs."""
        self._update_info()
        return [device for device in self.last_results]

    def get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""
        with self.lock:
            return self.last_results.get(mac)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Retrieve latest information from the Mikrotik box."""
        with self.lock:
            _LOGGER.info("Loading wireless device from Mikrotik...")

            wireless_clients = self.client(
                cmd='/interface/wireless/registration-table/getall'
            )
            device_names = self.client(cmd='/ip/dhcp-server/lease/getall')

            if device_names is None or wireless_clients is None:
                return False

            mac_names = {device.get('mac-address'): device.get('host-name')
                         for device in device_names
                         if device.get('mac-address')}

            self.last_results = {
                device.get('mac-address'):
                    mac_names.get(device.get('mac-address'))
                for device in wireless_clients
            }

            return True
