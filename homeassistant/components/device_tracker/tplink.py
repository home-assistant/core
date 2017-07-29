"""
Support for TP-Link routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.tplink/
"""
import base64
import hashlib
import logging
import re
import time

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

CONF_VERSION = "version"
CONF_MULTILOGIN_WAIT = "multiloginwait"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_VERSION, default=0):
        vol.Range(min=0, max=6),
    vol.Optional(CONF_MULTILOGIN_WAIT, default=60):
        vol.Range(min=0, max=300)
})


def get_scanner(hass, config):
    """Validate the configuration and return a TP-Link scanner."""
    scanners = [TplinkDeviceScanner, Tplink2DeviceScanner,
                Tplink3DeviceScanner, Tplink4DeviceScanner,
                Tplink5DeviceScanner, Tplink6DeviceScanner]
    cfg = config[DOMAIN]
    scannerversion = cfg[CONF_VERSION]
    if scannerversion == 0:
        for cls in scanners[::-1]:
            scanner = cls(cfg)
            if scanner.success_init:
                return scanner
    else:
        return scanners[scannerversion - 1](cfg)

    return None


def timems():
    """Return Unix Timestamp in milliseconds."""
    return int(time.time()*1000)


def md5hash(text):
    """Shortcut to calculate MD5 for text."""
    return hashlib.md5(text).hexdigest()


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
        self.success_init = self._update_info()

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    # pylint: disable=no-self-use
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
        password = md5hash(self.password.encode('utf')[:15])
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
                'cookie': cookie,
                'referer': referer
            })
            mac_results.extend(self.parse_macs.findall(page.text))

        if not mac_results:
            return False

        self.last_results = [mac.replace("-", ":") for mac in mac_results]
        return True


class Tplink5DeviceScanner(TplinkDeviceScanner):
    """This class queries a TP-Link EAP-225 AP with newer TP-Link FW."""

    def scan_devices(self):
        """Scan for new devices and return a list with found MAC IDs."""
        self._update_info()
        return self.last_results.keys()

    # pylint: disable=no-self-use
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
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12;"
                          " rv:53.0) Gecko/20100101 Firefox/53.0",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "Accept-Language: en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/x-www-form-urlencoded; "
                            "charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "http://" + self.host + "/",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        }

        password_md5 = md5hash(self.password.encode('utf')).upper()

        # create a session to handle cookie easier
        session = requests.session()
        session.get(base_url, headers=header)

        login_data = {"username": self.username, "password": password_md5}
        session.post(base_url, login_data, headers=header)

        # a timestamp is required to be sent as get parameter
        timestamp = timems()

        client_list_url = '{}/data/monitor.client.client.json'.format(
            base_url)

        get_params = {
            'operation': 'load',
            '_': timestamp
        }

        response = session.get(client_list_url,
                               headers=header,
                               params=get_params)
        session.close()
        try:
            list_of_devices = response.json()
        except ValueError:
            _LOGGER.error("AP didn't respond with JSON. "
                          "Check if credentials are correct.")
            return False

        if list_of_devices:
            self.last_results = {
                device['MAC'].replace('-', ':'): device['DeviceName']
                for device in list_of_devices['data']
                }
            return True

        return False


class Tplink6DeviceScanner(DeviceScanner):
    """This class queries a TP-Link TL-AP1308GI-PoE or simular device."""

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]

        self.parse_macs = re.compile('[0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2}-' +
                                     '[0-9A-F]{2}-[0-9A-F]{2}-[0-9A-F]{2}')

        self.host = host
        self.username = username
        self.password = password
        self.multiloginwait = config[CONF_MULTILOGIN_WAIT]

        self._session = requests.session()
        self._session.headers.update({
            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; "
                            "charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "http://" + self.host + "/",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache"
        })

        self.base_url = 'http://' + self.host
        self._login_url = self.base_url + "/data/version.json"
        self._login_confirm_url = self.base_url + \
            "/data/loginConfirm.json?_dc={}"
        self._version_url = self.base_url + "/data/version.json?_dc={}&id=10"
        self._station_url = self.base_url + \
            "/data/station.json?_dc={}&radioID={}"

        self._wait_login_until = 0
        self._loggedin = False
        self._confirm_login = False
        self.success_init = False

        self._radiocount = 0

        self.last_results = []

        self._update_info()

    def scan_devices(self):
        """Scan for new devices and return a list with found MAC IDs."""
        self._update_info()
        return self.last_results

    # pylint: disable=no-self-use
    def get_device_name(self, device):
        """Return. Feature does not supported."""
        return None

    def _login(self):
        """Login to router and get session code."""
        if self._wait_login_until > time.monotonic():
            return

        if self._confirm_login:
            response = self._session.get(
                self._login_confirm_url.format(timems()))
            self._loggedin = True
            self._confirm_login = False
            _LOGGER.warning("Login confirmed")
            return

        response = self._session.get(self._login_url)

        nonce = self._session.cookies['COOKIE']
        login_data = {
            "nonce": nonce,
            "encoded":
                self.username + ':' +
                md5hash(md5hash(self.password).upper() + ':' + nonce).upper()
            }

        response = self._session.post(self._login_url, login_data)

        try:
            loginresp = response.json()
        except ValueError:
            self.success_init = False
            self._loggedin = False
            self._session = requests.session()
            return

        if "success" not in loginresp:
            self.success_init = False
            self._loggedin = False
            return

        self.success_init = True
        if not loginresp["success"]:
            self._loggedin = False
            return
        status = loginresp["status"]
        if status == 0:
            self._loggedin = True
            return
        if status == 1:
            self._loggedin = False
            self._wait_login_until = time.monotonic() + 10
            return
        if status == 4:
            self._loggedin = False
            self._wait_login_until = time.monotonic() + self.multiloginwait
            self._confirm_login = True
            _LOGGER.warning("Login needs confirm. Wiat for {} seconds"
                            .format(self.multiloginwait))
            return
        self._loggedin = False
        return

    def _update_info(self):
        """Ensure the information from the TP-Link AP is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.info("Loading wireless clients...")

        if not self._loggedin:
            self._login()
            if not self._loggedin:
                return
        if self._radiocount == 0:
            for radioid in range(10):
                response = self._session.get(
                    self._station_url.format(timems(), radioid))

                try:
                    respjson = response.json()
                except ValueError:
                    return
                if not respjson["success"]:
                    self._radiocount = radioid
                    break
        devicelist = []
        for radioid in range(self._radiocount):
            response = self._session.get(
                self._station_url.format(timems(), radioid))
            try:
                respjson = response.json()
                if "status" in respjson:
                    self._loggedin = False
                    return
                resplist = respjson["data"]
                for device in resplist:
                    devicelist.append(device["mac"].replace('-', ':'))
            except ValueError:
                self._loggedin = False
                return

        self.last_results = devicelist
        return
