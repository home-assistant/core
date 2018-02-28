"""
Support for Huawei HiLink routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.huawei_hilink/
"""
import base64
import hashlib
import logging
from collections import namedtuple

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

REQUIREMENTS = ['defusedxml==0.5.0']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = '192.168.8.1'
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = 'admin'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string
})

SESSION_ID_COOKIE = 'SessionID'
VERIFICATION_TOKEN_HEADER = '__RequestVerificationToken'


# pylint: disable=unused-argument
def get_scanner(hass, config):
    """Validate the configuration and return a Huawei HiLink scanner."""
    scanner = HuaweiHiLinkDeviceScanner(config[DOMAIN])
    success_init = scanner.update_info()

    return scanner if success_init else None


Device = namedtuple('Device', ['name', 'mac', 'ip'])
AuthInfo = namedtuple('AuthInfo', ['session_id', 'verification_token'])


class HuaweiHiLinkDeviceScanner(DeviceScanner):
    """This class queries a Huawei HiLink router for wlan connected devices."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.api_location = 'http://{}/api'.format(self.host)
        self.auth_info = AuthInfo(session_id='wrong',
                                  verification_token='wrong')

        self.last_results = []
        _LOGGER.info("Scanner initialized")

    def scan_devices(self):
        """Scan for new devices."""
        self.update_info()
        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """Get device name from mac."""
        names = [device.name for device in self.last_results
                 if device.mac == mac]
        if names:
            return names[0]
        return None

    def update_info(self):
        """Ensure the information from the router is up to date.

        Retry once if fetching devices fails with fresh login. Return True if
        scanning successful.
        """
        _LOGGER.info("Scanning...")
        devices = _fetch_devices(self.api_location, self.auth_info)
        if devices is None:
            _LOGGER.info("Obtaining devices failed. Try to login")
            success_login = self._login()
            if not success_login:
                return False
            devices = _fetch_devices(self.api_location, self.auth_info)
            if devices is None:
                _LOGGER.warning("Fetching devices failed again. Stop")
                return False

        self.last_results = devices
        return True

    def _login(self):
        """Login and update authorization info.

        Retry once with fresh authorization info. Return True if login
        successful.
        """
        self.auth_info = _login(self.api_location,
                                self.username,
                                self.password,
                                self.auth_info)
        if self.auth_info is None:
            _LOGGER.info("Logging in failed. Try to obtain auth info again")
            self._obtain_auth_info()
            self.auth_info = _login(self.api_location,
                                    self.username,
                                    self.password,
                                    self.auth_info)
            if self.auth_info is None:
                _LOGGER.warning("Logging in failed with fresh auth info. Stop")
                return False

        return True

    def _obtain_auth_info(self):
        """Obtain and update authorization info."""
        self.auth_info = _obtain_auth_info(self.api_location)


def _obtain_auth_info(api_location):
    """Return authorization info with session id and verification token.

    Return None if operation not successful.
    """
    import defusedxml.ElementTree as ET

    _LOGGER.info("Obtaining session id and verification token")

    response = requests.get('{}/webserver/SesTokInfo'.format(api_location))
    xml_root = ET.fromstring(response.text)
    session_id_cookie = xml_root.findtext('SesInfo')
    session_id = session_id_cookie[len('{}='.format(SESSION_ID_COOKIE)):] \
        if session_id_cookie else None
    verification_token = xml_root.findtext('TokInfo')
    return AuthInfo(session_id, verification_token) \
        if session_id and verification_token else None


def _login(api_location, username, password, auth_info):
    """Login and return authorization with updated session id.

    Return None if login not successful.
    """
    _LOGGER.info("Logging in")

    password_hash = _hash_password(username,
                                   password,
                                   auth_info.verification_token)
    payload = """<?xml version="1.0" encoding="UTF-8"?>
<request>
    <Username>{}</Username>
    <Password>{}</Password>
    <password_type>4</password_type>
</request>""".format(username, password_hash)

    response = requests.post(
        '{}/user/login'.format(api_location),
        data=payload,
        cookies={SESSION_ID_COOKIE: auth_info.session_id},
        headers={VERIFICATION_TOKEN_HEADER: auth_info.verification_token}
    )

    success = '<response>OK</response>' in response.text
    return AuthInfo(
        response.cookies[SESSION_ID_COOKIE],
        auth_info.verification_token
    ) if success else None


def _hash_password(username, password, token):
    """Hash password."""
    # Reversed engineered based on main.js router script.
    result = hashlib.sha256(password.encode()).hexdigest()
    result = base64.b64encode(result.encode()).decode()
    result = username + result + token
    result = hashlib.sha256(result.encode()).hexdigest()
    result = base64.b64encode(result.encode()).decode()
    return result


def _fetch_devices(api_location, auth_info):
    """Fetch devices list.

    Return None if response cannot not be parsed.
    """
    import defusedxml.ElementTree as ET

    _LOGGER.info("Fetching devices")

    response = requests.get(
        '{}/wlan/host-list'.format(api_location),
        cookies={SESSION_ID_COOKIE: auth_info.session_id}
    )

    xml_root = ET.fromstring(response.text)
    hosts = xml_root.find('Hosts')
    if not hosts:
        return None
    return [_parse_device(host) for host in hosts]


def _parse_device(host):
    """Parse device information from host XML element."""
    return Device(
        name=host.findtext('HostName'),
        mac=host.findtext('MacAddress'),
        ip=host.findtext('IpAddress')
    )
