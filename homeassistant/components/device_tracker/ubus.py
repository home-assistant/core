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

# From http://lxr.mein.io/source/ubus/ubusmsg.h#L99
UBUS_STATUS_OK = 0
UBUS_STATUS_INVALID_COMMAND = 1
UBUS_STATUS_INVALID_ARGUMENT = 2
UBUS_STATUS_METHOD_NOT_FOUND = 3
UBUS_STATUS_NOT_FOUND = 4
UBUS_STATUS_NO_DATA = 5
UBUS_STATUS_PERMISSION_DENIED = 6
UBUS_STATUS_TIMEOUT = 7
UBUS_STATUS_NOT_SUPPORTED = 8
UBUS_STATUS_UNKNOWN_ERROR = 9
UBUS_STATUS_CONNECTION_FAILED = 10
UBUS_STATUS_NO_DATA = 5
UBUS_STATUS_PERMISSION_DENIED = 6


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
        username, password = config[CONF_USERNAME], config[CONF_PASSWORD]

        self.lock = threading.Lock()
        self.last_results = {}
        self.url = 'http://{}/ubus'.format(host)

        self.session_id = _get_session_id(self.url, username, password)
        self.success_init = self.session_id is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results.keys()

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def _update_info(self):
        if not self.success_init:
            return False

        with self.lock:
            _LOGGER.info("Checking DHCP leases..")

            self.last_results.clear()
            client_macs = []
            for v in ["ipv4leases", "ipv6leases"]:
                clients = _req_json_rpc(self.url, self.session_id,
                                    "call", "dhcp", v)
                #_LOGGER.error("clients: %s" % clients)
                for network in clients["device"]:
                    _LOGGER.debug("Checking network %s" % network)
                    for lease in clients["device"][network]["leases"]:
                        _LOGGER.debug("[%s] client: %s" % (network, lease))
                        client_macs.append(lease["mac"])
                        self.last_results[lease["mac"]] = lease

            _LOGGER.error("Scan found %s clients" % len(client_macs))

            return bool(client_macs)

        return False

    def get_device_name(self, device):
        _LOGGER.info("Getting name for %s", device)
        return self.last_results[device]["hostname"]

def _req_json_rpc(url, session_id, rpcmethod, subsystem, method, **params):
    """Perform one JSON RPC operation."""

    data = {"jsonrpc": "2.0",
            "id": 1,
            "method": rpcmethod,
            "params": [session_id,
                       subsystem,
                       method,
                       params]}
    data_json = json.dumps(data)
    _LOGGER.debug("> %s (%s)", data["method"], data["params"])

    try:
        res = requests.post(url, data=data_json, timeout=5)

    except requests.exceptions.Timeout:
        return

    _LOGGER.debug("< %s", res)

    if res.status_code == 200:
        response = res.json()

        if rpcmethod == "call":
            retcode = response["result"][0]
            if retcode != UBUS_STATUS_OK:
                if retcode == UBUS_STATUS_PERMISSION_DENIED:
                    _LOGGER.error("Not enough permissions!")
                    return
                elif retcode == UBUS_STATUS_NO_DATA:
                    _LOGGER.error("Empty leases file!")
                    return
                else:
                    _LOGGER.error("Got ubus error: %s" % retcode)
                    return

            if "error" in response:
                _LOGGER.error("Got error from ubus for call %s(%s): %s", data["method"], data["params"], response["error"])
                return response["error"]

            res = response["result"][1]
            return res
        else:
            return response["result"]


def _get_session_id(url, username, password):
    """Get the authentication token for the given host+username+password."""
    res = _req_json_rpc(url, "00000000000000000000000000000000", 'call',
                        'session', 'login', username=username,
                        password=password)
    #  TODO check for valid login!
    _LOGGER.error("Request and got token for %s?!: %s" % (username, res))
    return res["ubus_rpc_session"]
