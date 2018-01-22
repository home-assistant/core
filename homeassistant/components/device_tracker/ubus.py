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

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_DHCP_SOFTWARE = 'dhcp_software'
DEFAULT_DHCP_SOFTWARE = 'dnsmasq'
DHCP_SOFTWARES = [
    'dnsmasq',
    'odhcpd'
]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_DHCP_SOFTWARE, default=DEFAULT_DHCP_SOFTWARE):
        vol.In(DHCP_SOFTWARES),
})


def get_scanner(hass, config):
    """Validate the configuration and return an ubus scanner."""
    dhcp_sw = config[DOMAIN][CONF_DHCP_SOFTWARE]
    if dhcp_sw == 'dnsmasq':
        scanner = DnsmasqUbusDeviceScanner(config[DOMAIN])
    else:
        scanner = OdhcpdUbusDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


def _refresh_on_acccess_denied(func):
    """If remove rebooted, it lost our session so rebuld one and try again."""
    def decorator(self, *args, **kwargs):
        """Wrap the function to refresh session_id on PermissionError."""
        try:
            return func(self, *args, **kwargs)
        except PermissionError:
            _LOGGER.warning("Invalid session detected." +
                            " Trying to refresh session_id and re-run RPC")
            self.session_id = _get_session_id(
                self.url, self.username, self.password)

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
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")
        self.last_results = {}
        self.url = 'http://{}/ubus'.format(host)

        self.session_id = _get_session_id(
            self.url, self.username, self.password)
        self.hostapd = []
        self.mac2name = None
        self.success_init = self.session_id is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def _generate_mac2name(self):
        """Must be implemented depending on the software."""
        raise NotImplementedError

    @_refresh_on_acccess_denied
    def get_device_name(self, mac):
        """Return the name of the given device or None if we don't know."""
        if self.mac2name is None:
            self._generate_mac2name()
        name = self.mac2name.get(mac.upper(), None)
        self.mac2name = None
        return name

    @_refresh_on_acccess_denied
    def _update_info(self):
        """Ensure the information from the router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Checking hostapd")

        if not self.hostapd:
            hostapd = _req_json_rpc(
                self.url, self.session_id, 'list', 'hostapd.*', '')
            self.hostapd.extend(hostapd.keys())

        self.last_results = []
        results = 0
        for hostapd in self.hostapd:
            result = _req_json_rpc(
                self.url, self.session_id, 'call', hostapd, 'get_clients')

            if result:
                results = results + 1
                self.last_results.extend(result['clients'].keys())

        return bool(results)


class DnsmasqUbusDeviceScanner(UbusDeviceScanner):
    """Implement the Ubus device scanning for the dnsmasq DHCP server."""

    def __init__(self, config):
        """Initialize the scanner."""
        super(DnsmasqUbusDeviceScanner, self).__init__(config)
        self.leasefile = None

    def _generate_mac2name(self):
        if self.leasefile is None:
            result = _req_json_rpc(
                self.url, self.session_id, 'call', 'uci', 'get',
                config="dhcp", type="dnsmasq")
            if result:
                values = result["values"].values()
                self.leasefile = next(iter(values))["leasefile"]
            else:
                return

        result = _req_json_rpc(
            self.url, self.session_id, 'call', 'file', 'read',
            path=self.leasefile)
        if result:
            self.mac2name = dict()
            for line in result["data"].splitlines():
                hosts = line.split(" ")
                self.mac2name[hosts[1].upper()] = hosts[3]
        else:
            # Error, handled in the _req_json_rpc
            return


class OdhcpdUbusDeviceScanner(UbusDeviceScanner):
    """Implement the Ubus device scanning for the odhcp DHCP server."""

    def _generate_mac2name(self):
        result = _req_json_rpc(
            self.url, self.session_id, 'call', 'dhcp', 'ipv4leases')
        if result:
            self.mac2name = dict()
            for device in result["device"].values():
                for lease in device['leases']:
                    mac = lease['mac']  # mac = aabbccddeeff
                    # Convert it to expected format with colon
                    mac = ":".join(mac[i:i+2] for i in range(0, len(mac), 2))
                    self.mac2name[mac.upper()] = lease['hostname']
        else:
            # Error, handled in the _req_json_rpc
            return


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


def _get_session_id(url, username, password):
    """Get the authentication token for the given host+username+password."""
    res = _req_json_rpc(url, "00000000000000000000000000000000", 'call',
                        'session', 'login', username=username,
                        password=password)
    return res["ubus_rpc_session"]
