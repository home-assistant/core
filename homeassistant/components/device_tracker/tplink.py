"""
Support for TP-Link routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.tplink/
"""
import base64
import hashlib
import logging
import re
import threading
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.util import Throttle

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string
})


def get_scanner(hass, config):
    """Validate the configuration and return a TP-Link scanner."""
    for cls in [Tplink4DeviceScanner, Tplink3DeviceScanner,
                Tplink2DeviceScanner, TplinkDeviceScanner]:
        scanner = cls(config[DOMAIN])
        if scanner.success_init:
            return scanner

    return None


class TplinkDeviceScanner(DeviceScanner):
    """This class queries a wireless router running TP-Link firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]

        self.parse_macs = re.compile('[0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2}-' +
                                     '[0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2}')

        self.host = host
        self.username = username
        self.password = password

        self.last_results = {}
        self.lock = threading.Lock()
        self.success_init = self._update_info()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """Get firmware doesn't save the name of the wireless device."""
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
        with self.lock:
            _LOGGER.info("Loading wireless clients...")

            url = 'http://{}/userRpm/WlanStationRpm.htm'.format(self.host)
            referer = 'http://{}'.format(self.host)
            page = requests.get(
                url, auth=(self.username, self.password),
                headers={'referer': referer}, timeout=4)

            result = self.parse_macs.findall(page.text)

            if result:
                self.last_results = [mac.replace("-", ":") for mac in result]
                return True

            return False


class Tplink2DeviceScanner(TplinkDeviceScanner):
    """This class queries a router with newer version of TP-Link firmware."""

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results.keys()

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """Get firmware doesn't save the name of the wireless device."""
        return self.last_results.get(device)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
        with self.lock:
            _LOGGER.info("Loading wireless clients...")

            url = 'http://{}/data/map_access_wireless_client_grid.json' \
                .format(self.host)
            referer = 'http://{}'.format(self.host)

            # Router uses Authorization cookie instead of header
            # Let's create the cookie
            username_password = '{}:{}'.format(self.username, self.password)
            b64_encoded_username_password = base64.b64encode(
                username_password.encode('ascii')
            ).decode('ascii')
            cookie = 'Authorization=Basic {}' \
                .format(b64_encoded_username_password)

            response = requests.post(
                url, headers={'referer': referer, 'cookie': cookie},
                timeout=4)

            try:
                result = response.json().get('data')
            except ValueError:
                _LOGGER.error("Router didn't respond with JSON. "
                              "Check if credentials are correct.")
                return False

            if result:
                self.last_results = {
                    device['mac_addr'].replace('-', ':'): device['name']
                    for device in result
                    }
                return True

            return False


class Tplink3DeviceScanner(TplinkDeviceScanner):
    """This class queries the Archer C9 router with version 150811 or high."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.stok = ''
        self.sysauth = ''
        super(Tplink3DeviceScanner, self).__init__(config)

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        self._log_out()
        return self.last_results.keys()

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """Get the firmware doesn't save the name of the wireless device.

        We are forced to use the MAC address as name here.
        """
        return self.last_results.get(device)

    def _get_auth_tokens(self):
        """Retrieve auth tokens from the router."""
        _LOGGER.info("Retrieving auth tokens...")

        url = 'http://{}/cgi-bin/luci/;stok=/login?form=login' \
            .format(self.host)
        referer = 'http://{}/webpages/login.html'.format(self.host)

        # If possible implement rsa encryption of password here.
        response = requests.post(
            url, params={'operation': 'login', 'username': self.username,
                         'password': self.password},
            headers={'referer': referer}, timeout=4)

        try:
            self.stok = response.json().get('data').get('stok')
            _LOGGER.info(self.stok)
            regex_result = re.search(
                'sysauth=(.*);', response.headers['set-cookie'])
            self.sysauth = regex_result.group(1)
            _LOGGER.info(self.sysauth)
            return True
        except (ValueError, KeyError) as _:
            _LOGGER.error("Couldn't fetch auth tokens! Response was: %s",
                          response.text)
            return False

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
        with self.lock:
            if (self.stok == '') or (self.sysauth == ''):
                self._get_auth_tokens()

            _LOGGER.info("Loading wireless clients...")

            url = ('http://{}/cgi-bin/luci/;stok={}/admin/wireless?'
                   'form=statistics').format(self.host, self.stok)
            referer = 'http://{}/webpages/index.html'.format(self.host)

            response = requests.post(url,
                                     params={'operation': 'load'},
                                     headers={'referer': referer},
                                     cookies={'sysauth': self.sysauth},
                                     timeout=5)

            try:
                json_response = response.json()

                if json_response.get('success'):
                    result = response.json().get('data')
                else:
                    if json_response.get('errorcode') == 'timeout':
                        _LOGGER.info("Token timed out. Relogging on next scan")
                        self.stok = ''
                        self.sysauth = ''
                        return False
                    else:
                        _LOGGER.error(
                            "An unknown error happened while fetching data")
                        return False
            except ValueError:
                _LOGGER.error("Router didn't respond with JSON. "
                              "Check if credentials are correct")
                return False

            if result:
                self.last_results = {
                    device['mac'].replace('-', ':'): device['mac']
                    for device in result
                    }
                return True

            return False

    def _log_out(self):
        with self.lock:
            _LOGGER.info("Logging out of router admin interface...")

            url = ('http://{}/cgi-bin/luci/;stok={}/admin/system?'
                   'form=logout').format(self.host, self.stok)
            referer = 'http://{}/webpages/index.html'.format(self.host)

            requests.post(url,
                          params={'operation': 'write'},
                          headers={'referer': referer},
                          cookies={'sysauth': self.sysauth})
            self.stok = ''
            self.sysauth = ''


class Tplink4DeviceScanner(TplinkDeviceScanner):
    """This class queries an Archer C7 router with TP-Link firmware 150427."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.credentials = ''
        self.token = ''
        super(Tplink4DeviceScanner, self).__init__(config)

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """Get the name of the wireless device."""
        return None

    def _get_auth_tokens(self):
        """Retrieve auth tokens from the router."""
        _LOGGER.info("Retrieving auth tokens...")
        url = 'http://{}/userRpm/LoginRpm.htm?Save=Save'.format(self.host)

        # Generate md5 hash of password. The C7 appears to use the first 15
        # characters of the password only, so we truncate to remove additional
        # characters from being hashed.
        password = hashlib.md5(self.password.encode('utf')[:15]).hexdigest()
        credentials = '{}:{}'.format(self.username, password).encode('utf')

        # Encode the credentials to be sent as a cookie.
        self.credentials = base64.b64encode(credentials).decode('utf')

        # Create the authorization cookie.
        cookie = 'Authorization=Basic {}'.format(self.credentials)

        response = requests.get(url, headers={'cookie': cookie})

        try:
            result = re.search(r'window.parent.location.href = '
                               r'"https?:\/\/.*\/(.*)\/userRpm\/Index.htm";',
                               response.text)
            if not result:
                return False
            self.token = result.group(1)
            return True
        except ValueError:
            _LOGGER.error("Couldn't fetch auth tokens")
            return False

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
        with self.lock:
            if (self.credentials == '') or (self.token == ''):
                self._get_auth_tokens()

            _LOGGER.info("Loading wireless clients...")

            mac_results = []

            # Check both the 2.4GHz and 5GHz client list URLs
            for clients_url in ('WlanStationRpm.htm', 'WlanStationRpm_5g.htm'):
                url = 'http://{}/{}/userRpm/{}' \
                    .format(self.host, self.token, clients_url)
                referer = 'http://{}'.format(self.host)
                cookie = 'Authorization=Basic {}'.format(self.credentials)

                page = requests.get(url, headers={
                    'cookie': cookie,
                    'referer': referer
                })
                mac_results.extend(self.parse_macs.findall(page.text))

            if not mac_results:
                return False

            self.last_results = [mac.replace("-", ":") for mac in mac_results]
            return True
