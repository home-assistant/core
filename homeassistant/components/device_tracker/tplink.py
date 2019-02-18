"""
Support for TP-Link routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.tplink/
"""
import base64
from datetime import datetime
import hashlib
import logging
import re

from aiohttp.hdrs import (
    ACCEPT, COOKIE, PRAGMA, REFERER, CONNECTION, KEEP_ALIVE, USER_AGENT,
    CONTENT_TYPE, CACHE_CONTROL, ACCEPT_ENCODING, ACCEPT_LANGUAGE)
import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, HTTP_HEADER_X_REQUESTED_WITH)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['tplink==0.2.1']

_LOGGER = logging.getLogger(__name__)

HTTP_HEADER_NO_CACHE = 'no-cache'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string
})


def get_scanner(hass, config):
    """
    Validate the configuration and return a TP-Link scanner.

    The default way of integrating devices is to use a pypi

    package, The TplinkDeviceScanner has been refactored

    to depend on a pypi package, the other implementations

    should be gradually migrated in the pypi package

    """
    for cls in [
            TplinkDeviceScanner, Tplink5DeviceScanner, Tplink4DeviceScanner,
            Tplink3DeviceScanner, Tplink2DeviceScanner, Tplink1DeviceScanner
    ]:
        scanner = cls(config[DOMAIN])
        if scanner.success_init:
            return scanner

    return None


class TplinkDeviceScanner(DeviceScanner):
    """Queries the router for connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""
        from tplink.tplink import TpLinkClient
        host = config[CONF_HOST]
        password = config[CONF_PASSWORD]
        username = config[CONF_USERNAME]

        self.success_init = False
        try:
            self.tplink_client = TpLinkClient(
                password, host=host, username=username)

            self.last_results = {}

            self.success_init = self._update_info()
        except requests.exceptions.ConnectionError:
            _LOGGER.debug("ConnectionError in TplinkDeviceScanner")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results.keys()

    def get_device_name(self, device):
        """Get the name of the device."""
        return self.last_results.get(device)

    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.info("Loading wireless clients...")
        result = self.tplink_client.get_connected_devices()

        if result:
            self.last_results = result
            return True

        return False


class Tplink1DeviceScanner(DeviceScanner):
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
        self.success_init = False
        try:
            self.success_init = self._update_info()
        except requests.exceptions.ConnectionError:
            _LOGGER.debug("ConnectionError in Tplink1DeviceScanner")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """Get firmware doesn't save the name of the wireless device."""
        return None

    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.info("Loading wireless clients...")

        url = 'http://{}/userRpm/WlanStationRpm.htm'.format(self.host)
        referer = 'http://{}'.format(self.host)
        page = requests.get(
            url, auth=(self.username, self.password),
            headers={REFERER: referer}, timeout=4)

        result = self.parse_macs.findall(page.text)

        if result:
            self.last_results = [mac.replace("-", ":") for mac in result]
            return True

        return False


class Tplink2DeviceScanner(Tplink1DeviceScanner):
    """This class queries a router with newer version of TP-Link firmware."""

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results.keys()

    def get_device_name(self, device):
        """Get firmware doesn't save the name of the wireless device."""
        return self.last_results.get(device)

    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
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
            url, headers={REFERER: referer, COOKIE: cookie},
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


class Tplink3DeviceScanner(Tplink1DeviceScanner):
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

        # If possible implement RSA encryption of password here.
        response = requests.post(
            url, params={'operation': 'login', 'username': self.username,
                         'password': self.password},
            headers={REFERER: referer}, timeout=4)

        try:
            self.stok = response.json().get('data').get('stok')
            _LOGGER.info(self.stok)
            regex_result = re.search(
                'sysauth=(.*);', response.headers['set-cookie'])
            self.sysauth = regex_result.group(1)
            _LOGGER.info(self.sysauth)
            return True
        except (ValueError, KeyError):
            _LOGGER.error("Couldn't fetch auth tokens! Response was: %s",
                          response.text)
            return False

    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
        if (self.stok == '') or (self.sysauth == ''):
            self._get_auth_tokens()

        _LOGGER.info("Loading wireless clients...")

        url = ('http://{}/cgi-bin/luci/;stok={}/admin/wireless?'
               'form=statistics').format(self.host, self.stok)
        referer = 'http://{}/webpages/index.html'.format(self.host)

        response = requests.post(
            url, params={'operation': 'load'}, headers={REFERER: referer},
            cookies={'sysauth': self.sysauth}, timeout=5)

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
        _LOGGER.info("Logging out of router admin interface...")

        url = ('http://{}/cgi-bin/luci/;stok={}/admin/system?'
               'form=logout').format(self.host, self.stok)
        referer = 'http://{}/webpages/index.html'.format(self.host)

        requests.post(
            url, params={'operation': 'write'}, headers={REFERER: referer},
            cookies={'sysauth': self.sysauth})
        self.stok = ''
        self.sysauth = ''


class Tplink4DeviceScanner(Tplink1DeviceScanner):
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

        response = requests.get(url, headers={COOKIE: cookie})

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

    def _update_info(self):
        """Ensure the information from the TP-Link router is up to date.

        Return boolean if scanning successful.
        """
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
                COOKIE: cookie,
                REFERER: referer,
            })
            mac_results.extend(self.parse_macs.findall(page.text))

        if not mac_results:
            return False

        self.last_results = [mac.replace("-", ":") for mac in mac_results]
        return True


class Tplink5DeviceScanner(Tplink1DeviceScanner):
    """This class queries a TP-Link EAP-225 AP with newer TP-Link FW."""

    def scan_devices(self):
        """Scan for new devices and return a list with found MAC IDs."""
        self._update_info()
        return self.last_results.keys()

    def get_device_name(self, device):
        """Get firmware doesn't save the name of the wireless device."""
        return None

    def _update_info(self):
        """Ensure the information from the TP-Link AP is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.info("Loading wireless clients...")

        base_url = 'http://{}'.format(self.host)

        header = {
            USER_AGENT:
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12;"
                " rv:53.0) Gecko/20100101 Firefox/53.0",
            ACCEPT: "application/json, text/javascript, */*; q=0.01",
            ACCEPT_LANGUAGE: "Accept-Language: en-US,en;q=0.5",
            ACCEPT_ENCODING: "gzip, deflate",
            CONTENT_TYPE: "application/x-www-form-urlencoded; charset=UTF-8",
            HTTP_HEADER_X_REQUESTED_WITH: "XMLHttpRequest",
            REFERER: "http://{}/".format(self.host),
            CONNECTION: KEEP_ALIVE,
            PRAGMA: HTTP_HEADER_NO_CACHE,
            CACHE_CONTROL: HTTP_HEADER_NO_CACHE,
        }

        password_md5 = hashlib.md5(
            self.password.encode('utf')).hexdigest().upper()

        # Create a session to handle cookie easier
        session = requests.session()
        session.get(base_url, headers=header)

        login_data = {"username": self.username, "password": password_md5}
        session.post(base_url, login_data, headers=header)

        # A timestamp is required to be sent as get parameter
        timestamp = int(datetime.now().timestamp() * 1e3)

        client_list_url = '{}/data/monitor.client.client.json'.format(
            base_url)

        get_params = {
            'operation': 'load',
            '_': timestamp,
        }

        response = session.get(
            client_list_url, headers=header, params=get_params)
        session.close()
        try:
            list_of_devices = response.json()
        except ValueError:
            _LOGGER.error("AP didn't respond with JSON. "
                          "Check if credentials are correct")
            return False

        if list_of_devices:
            self.last_results = {
                device['MAC'].replace('-', ':'): device['DeviceName']
                for device in list_of_devices['data']
                }
            return True

        return False
