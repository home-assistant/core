"""
Support for Linksys Access Points.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.linksys_ap/
"""
import base64
import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL)

INTERFACES = 2
DEFAULT_TIMEOUT = 10

REQUIREMENTS = ['beautifulsoup4==4.6.0']

_LOGGER = logging.getLogger(__name__)

CONF_USE_COOKIES = 'enable_cookies'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_USE_COOKIES, default=False): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
})


def get_scanner(hass, config):
    """Validate the configuration and return a Linksys AP scanner."""
    try:
        return LinksysAPDeviceScanner(config[DOMAIN])
    except ConnectionError:
        return None


class LinksysAPDeviceScanner(DeviceScanner):
    """This class queries a Linksys Access Point."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.verify_ssl = config[CONF_VERIFY_SSL]
        self.use_cookies = config[CONF_USE_COOKIES]
        self.last_results = []
        self.session = requests.Session()
        
        # Check if the access point is accessible
        response = self._make_request()
        if not response.status_code == 200:
            raise ConnectionError("Cannot connect to Linksys Access Point")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return self.last_results

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """
        Return the name (if known) of the device.

        Linksys does not provide an API to get a name for a device,
        so we just return None
        """
        return None

    def _update_info(self):
        """Check for connected devices."""
        from bs4 import BeautifulSoup as BS

        if self.use_cookies:
            _LOGGER.info("Obtaining Linksys AP session cookie")

            login = base64.b64encode(bytes(self.username, 'utf8')).decode('ascii')
            pwd = base64.b64encode(bytes(self.password, 'utf8')).decode('ascii')
            creds = {'login_name': self.username, 'login_pwd': self.password, 'todo': 'login', 'h_lang': 'en', 'r_id': '', 'this_file': 'login.htm', 'next_file': 'Menu_Status.html'}
            url = 'https://{}/login.cgi'.format(self.host)
            self.session = requests.Session()
            response = self.session.post(url, data=creds, timeout=DEFAULT_TIMEOUT, verify=self.verify_ssl)        
            _LOGGER.info("The session cookie for Linksys AP is: " + response.cookies.get('session_id'))
        else:
            _LOGGER.info("Updating Linksys AP")

        self.last_results = []
        for interface in range(INTERFACES):
            request = self._make_request(interface)         
            self.last_results.extend(
                [x.find_all('td')[1].text
                 for x in BS(request.content, "html.parser")
                 .find_all(class_='section-row')]
            )
        
        return True

    def _make_request(self, unit=0):
        # No, the '&&' is not a typo - this is expected by the web interface.
        cookies = []
        if not self.use_cookies:
            login = base64.b64encode(bytes(self.username, 'utf8')).decode('ascii')
            pwd = base64.b64encode(bytes(self.password, 'utf8')).decode('ascii')
            cookies = {'LoginName': login, 'LoginPWD': pwd}
        
        url = 'https://{}/StatusClients.htm&&unit={}&vap=0'.format(
            self.host, unit)
        return self.session.get(
            url, timeout=DEFAULT_TIMEOUT, verify=self.verify_ssl, cookies=cookies)
