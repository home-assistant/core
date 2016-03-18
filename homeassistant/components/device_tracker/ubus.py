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

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import validate_config
from homeassistant.util import Throttle

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)


def get_scanner(hass, config):
    """Validate the configuration and return an ubus scanner."""
    if not validate_config(config,
                           {DOMAIN: [CONF_HOST, CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
        return None

    scanner = UbusDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


# pylint: disable=too-many-instance-attributes
class UbusDeviceScanner(object):
    """
    This class queries a wireless router running OpenWrt firmware.

    Adapted from Tomato scanner.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")
        self.lock = threading.Lock()
        self.last_results = {}
        self.url = 'http://{}/ubus'.format(host)

        self.session_id = _get_session_id(self.url, username, password)
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
                result = _req_json_rpc(self.url, self.session_id,
                                       'call', 'uci', 'get',
                                       config="dhcp", type="dnsmasq")
                if result:
                    values = result["values"].values()
                    self.leasefile = next(iter(values))["leasefile"]
                else:
                    return

            if self.mac2name is None:
                result = _req_json_rpc(self.url, self.session_id,
                                       'call', 'file', 'read',
                                       path=self.leasefile)
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
                hostapd = _req_json_rpc(self.url, self.session_id,
                                        'list', 'hostapd.*', '')
                self.hostapd.extend(hostapd.keys())

            self.last_results = []
            results = 0
            for hostapd in self.hostapd:
                result = _req_json_rpc(self.url, self.session_id,
                                       'call', hostapd, 'get_clients')

                if result:
                    results = results + 1
                    self.last_results.extend(result['clients'].keys())

            return bool(results)


def _req_json_rpc(url, session_id, rpcmethod, subsystem, method, **params):
    """Perform one JSON RPC operation."""
    data = json.dumps({"jsonrpc": "2.0",
                       "id": 1,
                       "method": rpcmethod,
                       "params": [session_id,
                                  subsystem,
                                  method,
                                  params]})

    try:
        res = requests.post(url, data=data, timeout=5)

    except requests.exceptions.Timeout:
        return

    if res.status_code == 200:
        response = res.json()

        if rpcmethod == "call":
            return response["result"][1]
        else:
            return response["result"]


def _get_session_id(url, username, password):
    """Get the authentication token for the given host+username+password."""
    res = _req_json_rpc(url, "00000000000000000000000000000000", 'call',
                        'session', 'login', username=username,
                        password=password)
    return res["ubus_rpc_session"]
