"""Support for Mikrotik routers as device tracker."""
import logging

import ssl

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_PORT, CONF_SSL, CONF_METHOD)

_LOGGER = logging.getLogger(__name__)

MTK_DEFAULT_API_PORT = '8728'
MTK_DEFAULT_API_SSL_PORT = '8729'

CONF_ENCODING = 'encoding'
DEFAULT_ENCODING = 'utf-8'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_METHOD): cv.string,
    vol.Optional(CONF_PORT): cv.port,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
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
        self.ssl = config[CONF_SSL]
        try:
            self.port = config[CONF_PORT]
        except KeyError:
            if self.ssl:
                self.port = MTK_DEFAULT_API_SSL_PORT
            else:
                self.port = MTK_DEFAULT_API_PORT
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.method = config.get(CONF_METHOD)
        self.encoding = config[CONF_ENCODING]

        self.connected = False
        self.success_init = False
        self.client = None
        self.wireless_exist = None
        self.success_init = self.connect_to_device()

        if self.success_init:
            _LOGGER.info("Start polling Mikrotik (%s) router...", self.host)
            self._update_info()
        else:
            _LOGGER.error("Connection to Mikrotik (%s) failed", self.host)

    def connect_to_device(self):
        """Connect to Mikrotik method."""
        import librouteros
        try:
            kwargs = {
                'port': self.port,
                'encoding': self.encoding
            }
            if self.ssl:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                kwargs['ssl_wrapper'] = ssl_context.wrap_socket
            self.client = librouteros.connect(
                self.host,
                self.username,
                self.password,
                **kwargs
            )

            try:
                routerboard_info = self.client(
                    cmd='/system/routerboard/getall')
            except (librouteros.exceptions.TrapError,
                    librouteros.exceptions.MultiTrapError,
                    librouteros.exceptions.ConnectionError):
                routerboard_info = None
                raise

            if routerboard_info:
                _LOGGER.info(
                    "Connected to Mikrotik %s with IP %s",
                    routerboard_info[0].get('model', 'Router'), self.host)

                self.connected = True

                try:
                    self.capsman_exist = self.client(
                        cmd='/caps-man/interface/getall')
                except (librouteros.exceptions.TrapError,
                        librouteros.exceptions.MultiTrapError,
                        librouteros.exceptions.ConnectionError):
                    self.capsman_exist = False

                if not self.capsman_exist:
                    _LOGGER.info(
                        "Mikrotik %s: Not a CAPSman controller. Trying "
                        "local interfaces", self.host)

                try:
                    self.wireless_exist = self.client(
                        cmd='/interface/wireless/getall')
                except (librouteros.exceptions.TrapError,
                        librouteros.exceptions.MultiTrapError,
                        librouteros.exceptions.ConnectionError):
                    self.wireless_exist = False

                if not self.wireless_exist and not self.capsman_exist \
                   or self.method == 'ip':
                    _LOGGER.info(
                        "Mikrotik %s: Wireless adapters not found. Try to "
                        "use DHCP lease table as presence tracker source. "
                        "Please decrease lease time as much as possible",
                        self.host)
                if self.method:
                    _LOGGER.info(
                        "Mikrotik %s: Manually selected polling method %s",
                        self.host, self.method)

        except (librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ConnectionError) as api_error:
            _LOGGER.error("Connection error: %s", api_error)
        return self.connected

    def scan_devices(self):
        """Scan for new devices and return a list with found device MACs."""
        import librouteros
        try:
            self._update_info()
        except (librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ConnectionError) as api_error:
            _LOGGER.error("Connection error: %s", api_error)
            self.connect_to_device()
        return [device for device in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        return self.last_results.get(device)

    def _update_info(self):
        """Retrieve latest information from the Mikrotik box."""
        if self.method:
            devices_tracker = self.method
        else:
            if self.capsman_exist:
                devices_tracker = 'capsman'
            elif self.wireless_exist:
                devices_tracker = 'wireless'
            else:
                devices_tracker = 'ip'

        _LOGGER.debug(
            "Loading %s devices from Mikrotik (%s) ...",
            devices_tracker, self.host)

        device_names = self.client(cmd='/ip/dhcp-server/lease/getall')
        if devices_tracker == 'capsman':
            devices = self.client(
                cmd='/caps-man/registration-table/getall')
        elif devices_tracker == 'wireless':
            devices = self.client(
                cmd='/interface/wireless/registration-table/getall')
        else:
            devices = device_names

        if device_names is None and devices is None:
            return False

        mac_names = {device.get('mac-address'): device.get('host-name')
                     for device in device_names if device.get('mac-address')}

        if devices_tracker in ('wireless', 'capsman'):
            self.last_results = {
                device.get('mac-address'):
                    mac_names.get(device.get('mac-address'))
                for device in devices}
        else:
            self.last_results = {
                device.get('mac-address'):
                    mac_names.get(device.get('mac-address'))
                for device in device_names if device.get('active-address')}

        return True
