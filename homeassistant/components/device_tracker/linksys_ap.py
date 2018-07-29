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

REQUIREMENTS = ['beautifulsoup4==4.6.1']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
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
        self.last_results = []

        # Check if the access point is accessible
        response = self._make_request()
        if not response.status_code == 200:
            raise ConnectionError("Cannot connect to Linksys Access Point")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return self.last_results

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

        _LOGGER.info("Checking Linksys AP")

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
        login = base64.b64encode(bytes(self.username, 'utf8')).decode('ascii')
        pwd = base64.b64encode(bytes(self.password, 'utf8')).decode('ascii')
        url = 'https://{}/StatusClients.htm&&unit={}&vap=0'.format(
            self.host, unit)
        return requests.get(
            url, timeout=DEFAULT_TIMEOUT, verify=self.verify_ssl,
            cookies={'LoginName': login, 'LoginPWD': pwd})
