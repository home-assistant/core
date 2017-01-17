"""
Support for Xiaomi Mi routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.xiaomi/
"""
import logging
import threading
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.util import Throttle

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME, default='admin'): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def get_scanner(hass, config):
    """Validate the configuration and return a Xiaomi Device Scanner."""
    scanner = XioamiDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class XioamiDeviceScanner(DeviceScanner):
    """This class queries a Xiaomi Mi router.

    Adapted from Luci scanner.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]

        self.lock = threading.Lock()

        self.last_results = {}
        self.token = _get_token(host, username, password)

        self.host = host

        self.mac2name = None
        self.success_init = self.token is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        with self.lock:
            if self.mac2name is None:
                url = "http://{}/cgi-bin/luci/;stok={}/api/misystem/devicelist"
                url = url.format(self.host, self.token)
                result = _get_device_list(url)
                if result:
                    hosts = [x for x in result
                             if 'mac' in x and 'name' in x]
                    mac2name_list = [
                        (x['mac'].upper(), x['name']) for x in hosts]
                    self.mac2name = dict(mac2name_list)
                else:
                    # Error, handled in the _req_json_rpc
                    return
            return self.mac2name.get(device.upper(), None)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the informations from the router are up to date.

        Returns true if scanning successful.
        """
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info('Refreshing device list')
            url = "http://{}/cgi-bin/luci/;stok={}/api/misystem/devicelist"
            url = url.format(self.host, self.token)
            result = _get_device_list(url)
            if result:
                self.last_results = []
                for device_entry in result:
                    # Check if the device is marked as connected
                    if int(device_entry['online']) == 1:
                        self.last_results.append(device_entry['mac'])

                return True

            return False


def _get_device_list(url, **kwargs):
    try:
        res = requests.get(url, timeout=5, **kwargs)
    except requests.exceptions.Timeout:
        _LOGGER.exception('Connection to the router timed out')
        return
    return _extract_result(res, 'list')


def _get_token(host, username, password):
    """Get authentication token for the given host+username+password."""
    url = 'http://{}/cgi-bin/luci/api/xqsystem/login'.format(host)
    data = {'username': username, 'password': password}
    try:
        res = requests.post(url, data=data, timeout=5)
    except requests.exceptions.Timeout:
        _LOGGER.exception('Connection to the router timed out')
        return
    return _extract_result(res, 'token')


def _extract_result(res, key_name):
    if res.status_code == 200:
        try:
            result = res.json()
        except ValueError:
            # If json decoder could not parse the response
            _LOGGER.exception('Failed to parse response from mi router')
            return
        try:
            return result[key_name]
        except KeyError:
            _LOGGER.exception('No %s in response from mi router. %s',
                              key_name, result)
            return
    else:
        _LOGGER.error('Invalid response from mi router: %s', res)
