# -*- coding: utf-8 -*-
"""
Support for French FAI Free routers.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.freebox/
"""

from collections import namedtuple
import logging
import voluptuous as vol
from datetime import timedelta
import json
import hmac
import hashlib
import urllib.request
import urllib.parse

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import DOMAIN, \
    PLATFORM_SCHEMA, DeviceScanner

from homeassistant.util import Throttle
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'http://mafreebox.freebox.fr/api/v4/'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Optional(CONF_HOST,
        default=DEFAULT_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string})


def get_scanner(hass, config):
    """Validate the configuration and return a Freebox scanner."""

    scanner = FreeboxDeviceScanner(config[DOMAIN])
    return (scanner if scanner.success_init else None)


Device = namedtuple('Device', ['mac', 'name', 'ip', 'last_update'])


class FreeboxDeviceScanner(DeviceScanner):

    """This class scans for devices connected to the bbox."""

    def __init__(self, config):
        """Initialize the scanner."""

        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        _LOGGER.info('Freebox - Credentials : ' + self.username + ' & '
                     + self.password)

        self.last_results = []  # type: List[Device]
        self.success_init = self._update_info()
        _LOGGER.info('Freebox - Scanner initialized')

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""

        self._update_info()
        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""

        filter_named = [device.name for device in self.last_results
                        if device.mac == mac]
        if filter_named:
            return filter_named[0]
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        username = self.username
        password = self.password
        token = bytes(password, 'latin-1')

        with urllib.request.urlopen(self.host + 'login/') as url:
            content = url.read().decode('UTF-8')
            challenge = json.loads(content)['result']['challenge']
            _LOGGER.info('Freebox - Challenge : ' + challenge)
            challenge = challenge.encode('utf-8')

        data = {'app_id': username, 'password': hmac.new(token,
                challenge, hashlib.sha1).hexdigest()}
        json_data = json.dumps(data)
        post_data = json_data.encode('utf-8')
        with urllib.request.urlopen(self.host + 'login/session/',
                                    post_data) as url:
            content = url.read().decode('UTF-8')
            session_token = json.loads(content)['result'
                    ]['session_token']
            _LOGGER.info('Freebox - Token : ' + session_token)

        now = dt_util.now()
        last_results = []

        headers = {}
        headers['X-Fbx-App-Auth'] = session_token
        req = urllib.request.Request(self.host + 'lan/browser/pub/',
                None, headers)
        res = urllib.request.urlopen(req).read().decode('UTF-8')
        resultat = json.loads(res)

        for device in resultat['result']:
            if device['active'] is True:
                last_results.append(Device(device['l2ident']['id'],
                                    device['names'][0]['name'],
                                    device['l3connectivities'][0]['addr'
                                    ], now))
                _LOGGER.info('Freebox - Device at Home : '
                             + device['names'][0]['name'])
        self.last_results = last_results
        _LOGGER.info('Freebox - Devices : Scan successful')
        return True
