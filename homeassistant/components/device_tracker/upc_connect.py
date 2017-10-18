"""
Support for UPC ConnectBox router.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.upc_connect/
"""
import asyncio
import logging

import aiohttp
import async_timeout
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession


REQUIREMENTS = ['defusedxml==0.5.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_IP = '192.168.0.1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_IP): cv.string,
})

CMD_DEVICES = 123


@asyncio.coroutine
def async_get_scanner(hass, config):
    """Return the UPC device scanner."""
    scanner = UPCDeviceScanner(hass, config[DOMAIN])
    success_init = yield from scanner.async_initialize_token()

    return scanner if success_init else None


class UPCDeviceScanner(DeviceScanner):
    """This class queries a router running UPC ConnectBox firmware."""

    def __init__(self, hass, config):
        """Initialize the scanner."""
        self.hass = hass
        self.host = config[CONF_HOST]

        self.data = {}
        self.token = None

        self.headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': "http://{}/index.html".format(self.host),
            'User-Agent': ("Mozilla/5.0 (Windows NT 10.0; WOW64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/47.0.2526.106 Safari/537.36")
        }

        self.websession = async_get_clientsession(hass)

    @asyncio.coroutine
    def async_scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        import defusedxml.ElementTree as ET

        if self.token is None:
            token_initialized = yield from self.async_initialize_token()
            if not token_initialized:
                _LOGGER.error("Not connected to %s", self.host)
                return []

        raw = yield from self._async_ws_function(CMD_DEVICES)

        try:
            xml_root = ET.fromstring(raw)
            return [mac.text for mac in xml_root.iter('MACAddr')]
        except (ET.ParseError, TypeError):
            _LOGGER.warning("Can't read device from %s", self.host)
            self.token = None
            return []

    @asyncio.coroutine
    def async_get_device_name(self, device):
        """The firmware doesn't save the name of the wireless device."""
        return None

    @asyncio.coroutine
    def async_initialize_token(self):
        """Get first token."""
        try:
            # get first token
            with async_timeout.timeout(10, loop=self.hass.loop):
                response = yield from self.websession.get(
                    "http://{}/common_page/login.html".format(self.host),
                    headers=self.headers
                )

                yield from response.text()

            self.token = response.cookies['sessionToken'].value

            return True

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Can not load login page from %s", self.host)
            return False

    @asyncio.coroutine
    def _async_ws_function(self, function):
        """Execute a command on UPC firmware webservice."""
        try:
            with async_timeout.timeout(10, loop=self.hass.loop):
                # The 'token' parameter has to be first, and 'fun' second
                # or the UPC firmware will return an error
                response = yield from self.websession.post(
                    "http://{}/xml/getter.xml".format(self.host),
                    data="token={}&fun={}".format(self.token, function),
                    headers=self.headers,
                    allow_redirects=False
                )

                # error?
                if response.status != 200:
                    _LOGGER.warning("Receive http code %d", response.status)
                    self.token = None
                    return

                # load data, store token for next request
                self.token = response.cookies['sessionToken'].value
                return (yield from response.text())

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error on %s", function)
            self.token = None
