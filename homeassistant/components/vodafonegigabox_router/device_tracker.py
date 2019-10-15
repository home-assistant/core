"""Support for Vodafone Gigabox routers."""
import logging
import re
import hashlib
import hmac
import time
from random import random
from collections import namedtuple

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return a Vodafone Gigabox scanner."""
    scanner = VodafoneDeviceScanner(config[DOMAIN])

    return scanner


Device = namedtuple("Device", ["name", "ip", "mac"])


class VodafoneDeviceScanner(DeviceScanner):
    """This class queries a Vodafone Gigabox router."""

    CSRF_REGEX = re.compile(r"csrf_token = '(.*?)'")
    VODAFONE_API_PASS = '$1$SERCOMM$'

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.csrf_token = None
        self.login_uid = None
        self.last_results = []

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._get_devices()
        return [client.mac for client in self.last_results]

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client.mac == device:
                return client.name
        return None

    def get_extra_attributes(self, device):
        """Return extra attributes for the given device or None if we don't know."""
        if not self.last_results:
            return None
        for client in self.last_results:
            if client.mac == device:
                return {'ip': client.ip}
        return None

    def _get_csrf(self):
        """Get CSRF token."""
        csrf = requests.get(
            f"http://{self.host}/login.html",
            headers={'Accept-Language': 'en-US,en;q=0.5'},
            verify=False
        )
        csrf_re = self.CSRF_REGEX.search(csrf.content.decode())
        return csrf_re.group(1)

    def _get_encrypted_pwd(self, key):
        """Get encrypted password."""
        passhash = hmac.new(
            self.VODAFONE_API_PASS.encode('utf-8'),
            msg=self.password.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        return hmac.new(
            key.encode('utf-8'),
            msg=passhash.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()

    def _get_url(self, path):
        """Get url with time and CSRF token set."""
        return f"http://{self.host}{path}?_={int(time.time()*1000)}&csrf_token={self.csrf_token}"

    def _get_devices(self):
        """Get the raw string with the devices from the router."""

        _LOGGER.debug("Logging in")

        # There is a multistep process for logging into the Vodafone Gigabox router
        #  1. Get CSRF token
        #  2. Get session password encryption key (so you're not sending the plaintext
        #     password, even over http)
        #  3. Reset something or other (not sure why, or even if, this is necessary)
        #  4. Login with username and password encrypted with session password encryption
        #     key
        #
        # Oh, and, by the way, you have to pass a timestamp in for each request.  I'm sure
        # someone thought it was a great idea

        # 1 . Get CSRF token
        self.csrf_token = self._get_csrf()
        self.login_uid = random()

        # 2. Get session password encryption key
        data_req = requests.get(
            self._get_url('/data/user_lang.json'),
            headers={'Accept-Language': 'en-US,en;q=0.5'},
            cookies={'login_uid': f"{self.login_uid}"},
            verify=False
        )
        data = data_req.json()
        key = None
        for item in data:
            if 'encryption_key' in item:
                key = item['encryption_key']
        password = self._get_encrypted_pwd(key)

        # 3. Reset the one thing, but not that thing, but the other thing
        requests.post(
            self._get_url('/data/reset.json'),
            headers={'Accept-Language': 'en-US,en;q=0.5'},
            data=[
                ("chk_sys_busy", ""),
            ],
            cookies={'login_uid': f"{self.login_uid}"},
            verify=False
        )

        # 4. Login!  Hurrah!
        login_req = requests.post(
            self._get_url('/data/login.json'),
            headers={'Accept-Language': 'en-US,en;q=0.5'},
            data=[
                ("LoginName", self.username),
                ("LoginPWD", password)
            ],
            cookies={'login_uid': f"{self.login_uid}"},
            verify=False
        )

        # Get router overview, including clients
        session = login_req.cookies['session_id']
        overview_req = requests.get(
            self._get_url('/data/overview.json'),
            headers={'Accept-Language': 'en-US,en;q=0.5'},
            cookies={'login_uid': f"{self.login_uid}", 'session_id': session},
            verify=False
        )

        clients = []

        # This is "JSON", but not really.  Why?
        wifi_clients = None
        for i in overview_req.json():
            if 'wifi_user' in i:
                wifi_clients = i['wifi_user']

        # Someone doesn't understand what JSON is, so let's parse the wifi clients into a 2D array
        wifi_clients = wifi_clients.split(';')
        for i in wifi_clients:
            if len(i) == 0:
                continue
            item = i.split('|')
            if item[0].lower() != 'on':
                continue
            clients.append(Device(
                item[2],
                item[4],
                item[3]
            ))

        self.last_results = clients
