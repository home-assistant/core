import re
import hmac
import logging
import hashlib
import requests
from bs4 import BeautifulSoup

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, HTTP_HEADER_X_REQUESTED_WITH)
import homeassistant.helpers.config_validation as cv

import voluptuous as vol

REQUIREMENTS = ['beautifulsoup4']

_LOGGER = logging.getLogger(__name__)

HTTP_HEADER_NO_CACHE = 'no-cache'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string
})

def get_scanner(hass, config):
    """Validate the configuration and return a Tilgin Device Scanner."""

    models = [ TilginHG238xDeviceScanner ]
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

        try:
            self.success_init = self._check_auth()
        except:
            _LOGGER.debug("ConnectionError in TilginDeviceScanner")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results.keys()

    def get_device_name(self, device):
        """Get the name of the device."""
        return self.last_results.get(device)

    def _check_auth(self):
        self._authenticate()
        r = self.session.get(self.url)
        if 'You are logged in as' in r.text:
            return True
        else:
            return False

    def _authenticate(self):
        """Extract the HMAC key and auth to the device"""

        r = self.session.get(self.url)
        soup = BeautifulSoup(r.content, 'html.parser')
        hmac_key = re.search('__pass\.value,\s+"(\w+?)"', soup.text).group(1)
        _LOGGER.debug("hmac_key: {}".format(hmac_key))

        # Calculate the login HMAC
        hashed_login = hmac.new(bytes(hmac_key, 'ascii'), (self.username + self.password).encode("utf8"), hashlib.sha1)

        login_data = { '__hash': hashed_login.hexdigest(), '__user': self.username, '__auth': 'login', '__formtok':''}

        self.session.post(self.url, data=login_data, allow_redirects=False)

    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.
        Return boolean if scanning successful.
        """

        _LOGGER.info("Loading LAN clients...")

        r = self.session.get(self.url + '/status/lan_clients/')
        if r.status_code == 403:
            self._authenticate()
            r = self.session.get(self.url + '/status/lan_clients/')
            if r.status_code == 403:
                return False

        soup = BeautifulSoup(r.content, 'html.parser')
        clients_html = soup.find('table', {"class": "control"})
        devices = clients_html.findAll('tr')[1:]

        self.last_results = {
            device.findAll('td')[2].text.strip(u'\u200e'): device.findAll('td')[1].text
            for device in devices if 'Active' in device.findAll('td')[0].text
        }
        return True
