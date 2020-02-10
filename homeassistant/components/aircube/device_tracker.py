"""Support for Ubiquiti airCube routers."""
import json
import logging
import re

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return an airCube scanner."""
    scanner = AirCubeDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


def _refresh_on_access_denied(func):
    """If session timed out, need new session_id."""

    def decorator(self, *args, **kwargs):
        """Wrap the function to refresh session_id on error."""
        try:
            return func(self, *args, **kwargs)
        except (
            PermissionError,
            KeyError,
            NameError,
            requests.exceptions.ConnectionError,
        ):
            _LOGGER.debug(
                "Possible authentication error."
                "Trying to refresh session_id and rerun."
            )
            self.session_id = _get_session_id(
                self.url, self.username, self.password, self.verify_ssl
            )
            return func(self, *args, **kwargs)

    return decorator


class AirCubeDeviceScanner(DeviceScanner):
    """
    This class queries an Ubiquiti airCube wireless router.

    Script adapted from ubus (OpenWrt) device tracker.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.verify_ssl = config[CONF_VERIFY_SSL]

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")
        self.last_results = {}
        self.url = f"https://{host}/ubus"

        self.session_id = _get_session_id(
            self.url, self.username, self.password, self.verify_ssl
        )
        self.clients = []
        self.mac2name = None
        self.success_init = self.session_id is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def _generate_mac2name(self):
        """Return empty MAC to name dict."""
        self.mac2name = dict()

    @_refresh_on_access_denied
    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if self.mac2name is None:
            self._generate_mac2name()
        if self.mac2name is None:
            return None
        name = self.mac2name.get(device.upper(), None)
        return name

    @_refresh_on_access_denied
    def _update_info(self):
        """
        Ensure the information from the router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Checking for clients")

        self.last_results = []
        results = 0

        result = _req_json_rpc(
            self.url, self.session_id, "call", "ubnt", "stats", self.verify_ssl
        )

        mac_data0 = result["result"][1]["results"]["wireless"]["interface"]["wlan0"][
            "assoclist"
        ]
        for i in mac_data0:
            self.last_results.append(i["mac"])
            results = results + 1
        # Only airCube AC has 5GHz radio
        try:
            mac_data1 = result["result"][1]["results"]["wireless"]["interface"][
                "wlan1"
            ]["assoclist"]
            for i in mac_data1:
                self.last_results.append(i["mac"])
                results = results + 1
        except KeyError:
            pass

        return bool(results)


def _req_json_rpc(url, session_id, rpcmethod, subsystem, method, verify_ssl, **params):
    """Perform one JSON RPC operation."""
    data = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": rpcmethod,
            "params": [session_id, subsystem, method, params],
        }
    )

    try:
        res = requests.post(url, data=data, timeout=5, verify=verify_ssl)

    except (requests.exceptions.Timeout):
        _LOGGER.warning(
            "Connection to airCube timed out. Check that IP address is correct"
            "and that device is accessible."
        )
    except (requests.exceptions.SSLError):
        _LOGGER.warning("SSL error. Set VERIFY_SSL to False.")
    except (requests.exceptions.ConnectionError):
        _LOGGER.warning("Error connecting to airCube.")
    else:
        return res.json()


def _get_session_id(url, username, password, verify_ssl):
    """Get the authentication token for the given host+username+password."""
    res = []
    try:
        res = _req_json_rpc(
            url,
            "00000000000000000000000000000000",
            "call",
            "session",
            "login",
            verify_ssl=verify_ssl,
            username=username,
            password=password,
        )
    finally:
        pass
    if res is not None:
        try:
            return res["result"][1]["ubus_rpc_session"]
        except IndexError:
            return _LOGGER.warning("Authentication error: Check username and password.")
