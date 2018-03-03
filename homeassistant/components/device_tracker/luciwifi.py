"""
Support for OpenWRT (luci) routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.luciwifi/
"""
import logging
import requests
import urllib3
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_SSL, CONF_VERIFY_SSL)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_LOGGER = logging.getLogger(__name__)

CONF_RADIO = 'radio'
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(
        CONF_RADIO, default='radio0.network1,radio1.network1'): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): vol.Any(
        cv.boolean, cv.isfile),
    vol.Optional(CONF_SSL, default=False): cv.boolean
})


def get_scanner(hass, config):
    """Validate the configuration and return a Luci scanner."""
    scanner = LuciWifiDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class LuciWifiDeviceScanner(DeviceScanner):
    """This class queries a wireless router running OpenWrt firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.radio = config[CONF_RADIO]
        self.verify = config[CONF_VERIFY_SSL]
        if config[CONF_SSL]:
            self.proto = 'https'
        else:
            self.proto = 'http'
        self.last_results = []
        self.success_init = self.login()
        _LOGGER.info("Starting luci wifi scanner {}://{} radio:{}".format(
            self.proto, self.host, self.radio))

    def login(self):
        """Try to login to luci."""
        self.session = requests.Session()
        url = '{}://{}/cgi-bin/luci/'.format(self.proto, self.host)
        data = {'luci_username': self.username, 'luci_password': self.password}
        try:
            res = self.session.post(url, data=data,
                                    verify=self.verify, timeout=5)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exception:
            _LOGGER.error("Cannot login {}://{} : {}".format(
                self.proto, self.host, exception.__class__.__name__))
            return False
        if res.status_code == 302 or res.status_code == 200:
            _LOGGER.debug("login {}://{} status_code: {} succeeded".format(
                self.proto, self.host, res.status_code))
            return True
        else:
            _LOGGER.error("Cannot login to {}://{} status_code: {}".format(
                self.proto, self.host, res.status_code))
        return False

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    @staticmethod
    def get_device_name(device):
        """Return the name of the given device or None if we don't know."""
        return device.lower()

    def _update_info(self):
        """Ensure the information from the Luci router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        url = '{}://{}/cgi-bin/luci/admin/network/wireless_status/{}'.format(
            self.proto, self.host, self.radio)
        try:
            res = self.session.get(url, verify=self.verify, timeout=5)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as exception:
            _LOGGER.error("Cannot retrieve json from {}://{} : {}".format(
                self.proto, self.host,exception.__class__.__name__))
            return False
        if res.status_code != 200:
            _LOGGER.info("Logging in again, responsecode: {}".format(
                res.status_code))
            self.login()
            return False

        try:
            result = res.json()
        except ValueError:
            _LOGGER.exception("Failed to parse response from luci")
            return False

        try:
            results = []
            for radio in result:
                for k in radio['assoclist']:
                    results.append(k)
            self.last_results = results
            return True
        except KeyError:
            _LOGGER.exception("No result in response from luci")
        return False
