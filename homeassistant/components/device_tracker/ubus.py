"""
Support for OpenWRT (ubus) routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.ubus/
"""
import json
import logging
import re

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_SSL
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

CONF_SSL_VERIFY = 'sslverify'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_SSL_VERIFY, default=False): cv.boolean
})


def get_scanner(hass, config):
    """Validate the configuration and return an ubus scanner."""
    scanner = UbusDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


def _refresh_on_acccess_denied(func):
    """If remove rebooted, it lost our session so rebuld one and try again."""
    def decorator(self, *args, **kwargs):
        """Wrapper function to refresh session_id on PermissionError."""
        try:
            return func(self, *args, **kwargs)
        except PermissionError:
            _LOGGER.warning("Invalid session detected." +
                            " Tryign to refresh session_id and re-run the rpc")
            self.session_id = self.get_session_id()

            return func(self, *args, **kwargs)

    return decorator


class UbusDeviceScanner(DeviceScanner):
    """
    This class queries a wireless router running OpenWrt firmware.

    Adapted from Tomato scanner.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        ssl = config[CONF_SSL]
        self.ssl_verify = config[CONF_SSL_VERIFY]

        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")
        self.last_results = {}
        if not ssl:
            self.url = 'http://{}/ubus'.format(host)
        else:
            self.url = 'https://{}/ubus'.format(host)

        self.session_id = self.get_session_id()
        self.hostapd = []
        self.leasefile = None
        self.mac2name = None
        self.success_init = self.session_id is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    @_refresh_on_acccess_denied
    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if self.leasefile is None:
            result = self._req_json_rpc('call', 'uci', 'get',
                                        config="dhcp", type="dnsmasq")
            if result:
                values = result["values"].values()
                self.leasefile = next(iter(values))["leasefile"]
            else:
                return

        _LOGGER.debug("loading name for "+device)
        if self.mac2name is None:
            result = self._req_json_rpc('call', 'file', 'read',
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

    @_refresh_on_acccess_denied
    def _update_info(self):
        """Ensure the information from the Luci router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        self.mac2name = None

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
        data = json.dumps({"jsonrpc": "2.0",
                           "id": 1,
                           "method": rpcmethod,
                           "params": [self.session_id,
                                      subsystem,
                                      method,
                                      params]})

        try:
            res = requests.post(self.url, data=data, timeout=5, verify=self.ssl_verify)

        except requests.exceptions.Timeout:
            return

        if res.status_code == 200:
            response = res.json()
            if 'error' in response:
                if 'message' in response['error'] and \
                        response['error']['message'] == "Access denied":
                    raise PermissionError(response['error']['message'])
                else:
                    raise HomeAssistantError(response['error']['message'])

            if rpcmethod == "call":
                try:
                    return response["result"][1]
                except IndexError:
                    return
            else:
                return response["result"]

        _LOGGER.warn(self.url, data)


    def get_session_id(self):
        """Get the authentication token for the given host+username+password."""
        self.session_id = "00000000000000000000000000000000"
        res = self._req_json_rpc('call', 'session', 'login', username=self.username,
                                 password=self.password)
        return res["ubus_rpc_session"]


if __name__ == "__main__":
    from tplink import Tplink6DeviceScanner
    import time
    
    x = Tplink6DeviceScanner({CONF_USERNAME:"admin", CONF_HOST:"192.168.102.254", CONF_PASSWORD:"routeadmin11"})
    u = UbusDeviceScanner({CONF_HOST:"192.168.102.1", CONF_USERNAME:"root",CONF_PASSWORD:"routeadmin11",CONF_SSL:True, CONF_SSL_VERIFY:False})
    for _ in range(20):
        t = x.scan_devices()
        for i in t:
            print(u.get_device_name(i))
        time.sleep(5)