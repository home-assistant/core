"""
Support for OpenWRT (ubus) routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ubus/
"""
import json
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

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string
})

# From:
# http://git.openwrt.org/?p=project/uhttpd.git;a=blob;f=ubus.c;hb=a8bf9c00842224edb394e79909053f7628ee6a82#l103
_ERROR_ACCESS_DENIED = -32002

_NULL_SESSION_ID = "00000000000000000000000000000000"


def get_scanner(hass, config):
    """Validate the configuration and return an ubus scanner."""
    scanner = UbusDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class UbusDeviceScanner(DeviceScanner):
    """
    This class queries a wireless router running OpenWrt firmware.

    Adapted from Tomato scanner.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")
        self.lock = threading.Lock()
        self.last_results = {}
        self.url = 'http://{}/ubus'.format(host)

        self._get_new_session_id()
        self.hostapd = []
        self.leasefile = None
        self.mac2name = None
        self.success_init = self.session_id is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        with self.lock:
            if self.leasefile is None:
                result = self._req_json_rpc(
                    'call', 'uci', 'get', config="dhcp", type="dnsmasq")
                if result:
                    values = result["values"].values()
                    self.leasefile = next(iter(values))["leasefile"]
                else:
                    return

            if self.mac2name is None:
                result = self._req_json_rpc(
                    'call', 'file', 'read', path=self.leasefile)
                if result:
                    self.mac2name = dict()
                    for line in result["data"].splitlines():
                        hosts = line.split(" ")
                        self.mac2name[hosts[1].upper()] = hosts[3]
                else:
                    # Error, handled in the _req_json_rpc
                    return

            return self.mac2name.get(device.upper(), None)

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        """Ensure the information from the Luci router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info("Checking ARP")

            if not self.hostapd:
                hostapd = self._req_json_rpc('list', 'hostapd.*', '')
                self.hostapd.extend(hostapd.keys())

            self.last_results = []
            results = 0
            for hostapd in self.hostapd:
                result = self._req_json_rpc('call', hostapd, 'get_clients')

                if result:
                    results = results + 1
                    self.last_results.extend(result['clients'].keys())

            return bool(results)

    def _req_json_rpc(self, rpcmethod, subsystem, method, **params):
        """Perform one JSON RPC operation."""
        retry_count = 2
        while retry_count >= 0:
            retry_count -= 1
            data = json.dumps({"jsonrpc": "2.0",
                               "id": 1,
                               "method": rpcmethod,
                               "params": [self.session_id,
                                          subsystem,
                                          method,
                                          params]})

            try:
                res = requests.post(self.url, data=data, timeout=5)

            except requests.exceptions.Timeout:
                return

            if res.status_code != 200:
                return
            response = res.json()

            if rpcmethod != "call":
                return response["result"]
            error = response.get("error", None)
            if error is not None:
                error_code = error["code"]
                error_message = error["message"]
                have_session_id = self.session_id != _NULL_SESSION_ID
                access_denied = error_code == _ERROR_ACCESS_DENIED
                if access_denied and have_session_id:
                    _LOGGER.info(
                        "Session has expired, requesting new session")
                    self._get_new_session_id()
                    # Retry the request with the new session id
                    continue
                else:
                    _LOGGER.error("Request failed %d: %s",
                                  error_code, error_message)
                    return
            try:
                return response["result"][1]
            except IndexError:
                # Indicates a blank response from the server
                return

    def _get_new_session_id(self):
        """Get a new authentication token (aka session id)."""
        self.session_id = _NULL_SESSION_ID
        res = self._req_json_rpc(
            'call', 'session', 'login',
            username=self.username, password=self.password)
        self.session_id = res["ubus_rpc_session"]
