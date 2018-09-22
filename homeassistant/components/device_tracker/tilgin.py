"""
Support for Tilgin routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.tilgen/
"""

import re
import hmac
import logging
import hashlib
import requests

import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['beautifulsoup4==4.6.3']

_LOGGER = logging.getLogger(__name__)

HTTP_HEADER_NO_CACHE = 'no-cache'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string
})


def get_scanner(hass, config):
    """Validate the configuration and return a Tilgin Device Scanner."""
    models = [TilginHG238xDeviceScanner]
    for model_family in models:
        scanner = model_family(config[DOMAIN])
        if scanner.success_init:
            return scanner

    return None


class TilginHG238xDeviceScanner(DeviceScanner):
    """Queries the router for connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.url = 'http://{}'.format(config[CONF_HOST])
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.session = requests.Session()

        self.last_results = {}
        self.success_init = False

        _LOGGER.debug("Initialising Tilgin HG238x Device")
        self.success_init = self._check_auth()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results.keys()

    def get_device_name(self, device):
        """Get the name of the device."""
        return self.last_results.get(device)

    def _check_auth(self):
        """Check the credentials work."""
        self._authenticate()
        res = self.session.get(self.url)
        if 'You are logged in as' in res.text:
            _LOGGER.debug("auth success")
            return True
        _LOGGER.debug("auth failure")
        return False

    def _authenticate(self):
        """Extract the HMAC key and auth to the device."""
        from bs4 import BeautifulSoup

        _LOGGER.debug("Starting auth")
        res = self.session.get(self.url + '/status/lan_clients/')
        if 'You are logged in as' in res.text:
            _LOGGER.debug("already authenticated")
            return
        soup = BeautifulSoup(res.content, 'html.parser')
        hmac_key = re.search(r'__pass\.value,\s+"(\w+?)"', soup.text).group(1)
        hmac_message = (self.username + self.password).encode("utf8")

        _LOGGER.debug("hmac_key: %s", hmac_key)

        # Calculate the login HMAC
        hashed_login = hmac.new(bytes(hmac_key, 'ascii'),
                                hmac_message,
                                hashlib.sha1
                                )

        login_data = {'__hash': hashed_login.hexdigest(),
                      '__user': self.username,
                      '__auth': 'login',
                      '__formtok': ''
                      }

        self.session.post(self.url, data=login_data, allow_redirects=False)

    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
        from bs4 import BeautifulSoup

        _LOGGER.info("Loading LAN clients...")

        res = self.session.get(self.url + '/status/lan_clients/')
        if res.status_code == 403:
            self._authenticate()
            res = self.session.get(self.url + '/status/lan_clients/')
            if res.status_code == 403:
                return False

        soup = BeautifulSoup(res.content, 'html.parser')
        clients_html = soup.find('table', {"class": "control"})
        devices = clients_html.findAll('tr')[1:]

        self.last_results = {}

        for device in devices:
            device = device.findAll('td')
            if 'Active' not in device[0].text:
                continue
            device_mac = device[2].text.strip(u'\u200e')
            device_name = device[1].text
            _LOGGER.debug('%s: %s', device_name, device_mac)
            self.last_results[device_mac] = device_name

        _LOGGER.debug("Found %d devices", len(self.last_results))
        return True
