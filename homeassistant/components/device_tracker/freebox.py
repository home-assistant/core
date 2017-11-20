"""
Support for French FAI Free routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.freebox/
"""
from collections import namedtuple
from datetime import timedelta
import hashlib
import hmac
import json
import logging
import urllib.parse
import urllib.request

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def get_scanner(hass, config):
    """Validate the configuration and return a Freebox scanner."""
    scanner = FreeboxDeviceScanner(config[DOMAIN])
    return scanner if scanner.success_init else None


Device = namedtuple('Device', ['mac', 'name', 'ip', 'last_update'])


class FreeboxDeviceScanner(DeviceScanner):
    """This class scans for devices connected to the Freebox."""

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]+"/api/v4/"
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.token = "0"
        _LOGGER.debug("Freebox - Credentials : " + self.username +
                      " & " + self.password)

        self.last_results = []
        self.success_init = self._update_info()
        _LOGGER.info("Freebox - Scanner initialized")

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return [device.mac for device in self.last_results]

    def get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""
        filter_named = [device.name for device in self.last_results if
                        device.mac == mac]
        if filter_named:
            return filter_named[0]
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Check the Freebox for devices.

        Returns boolean if scanning successful.
        """
        host = self.host
        username = self.username
        password = bytes(self.password, 'latin-1')
        session_token = self.token

        if session_token != "0":
            # Is my session stil active ?
            headers = {}
            headers['X-Fbx-App-Auth'] = session_token
            full_host = host+"lan/browser/pub/"
            req = urllib.request.Request(full_host, None, headers)
            try:
                res = urllib.request.urlopen(req)
                resultat = json.loads(res.read().decode('UTF-8'))
            except urllib.error.HTTPError as err:
                _LOGGER.debug("Freebox - HTTPError : "+err.msg)
                session_token = "0"

        if session_token == "0" or resultat["success"] is False:
            # I have no active session so I login
            full_host = host+"login/"
            with urllib.request.urlopen(full_host) as url:
                content = url.read().decode('UTF-8')
                challenge = json.loads(content)["result"]["challenge"]
                _LOGGER.debug("Freebox - Challenge : "+challenge)

            data = {"app_id": username,
                    "password": hmac.new(password,
                                         challenge.encode('utf-8'),
                                         hashlib.sha1).hexdigest()}
            json_data = json.dumps(data)
            full_host = host+"login/session/"
            with urllib.request.urlopen(full_host,
                                        json_data.encode('utf-8')) as url:
                content = url.read().decode('UTF-8')
                json_session = json.loads(content)
                new_token = json_session["result"]["session_token"]
                _LOGGER.debug("Freebox - Token : "+new_token)
                self.token = new_token

        # I ask the router for connected devices
        headers = {}
        headers['X-Fbx-App-Auth'] = self.token
        full_host = host+"lan/browser/pub/"
        req = urllib.request.Request(full_host, None, headers)
        res = urllib.request.urlopen(req).read().decode('UTF-8')
        resultat = json.loads(res)

        last_results = []
        now = dt_util.now()

        if resultat['success'] is True:
            for device in resultat["result"]:
                if device['active'] is True:
                    try:
                        last_results.append(Device(
                            device['l2ident']['id'],
                            device['names'][0]['name'],
                            device['l3connectivities'][0]['addr'],
                            now))
                        _LOGGER.debug("Freebox - Device at Home : " +
                                      device['names'][0]['name'])
                    except KeyError as keyerror:
                        _LOGGER.debug("Freebox - Error scanning : " +
                                      str(keyerror))
            self.last_results = last_results
            _LOGGER.info("Freebox - Devices : Scan successful")
            return True

        return False
