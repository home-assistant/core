"""
Support for OpenWRT (luci) routers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.luci/
"""
import json
import logging
import re

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.exceptions import HomeAssistantError
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SSL)

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean
})


class InvalidLuciTokenError(HomeAssistantError):
    """When an invalid token is detected."""

    pass


class LuciRpcMethodNotFoundError(HomeAssistantError):
    """When an invalid method is called."""

    pass


def get_scanner(hass, config):
    """Validate the configuration and return a Luci scanner."""
    scanner = LuciDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class LuciDeviceScanner(DeviceScanner):
    """This class queries a wireless router running OpenWrt firmware."""

    def __init__(self, config):
        """Initialize the scanner."""
        host = config[CONF_HOST]
        protocol = 'http' if not config[CONF_SSL] else 'https'
        self.origin = '{}://{}'.format(protocol, host)
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.parse_api_pattern = re.compile(r"(?P<param>\w*) = (?P<value>.*);")

        self.last_results = {}
        self.refresh_token()
        self.mac2name = None
        self.success_init = self.token is not None
        self.use_ip_neighbors_table = False

    def refresh_token(self):
        """Get a new token."""
        self.token = _get_token(self.origin, self.username, self.password)

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if self.mac2name is None:
            url = '{}/cgi-bin/luci/rpc/uci'.format(self.origin)
            result = _req_json_rpc(
                url, 'get_all', 'dhcp', params={'auth': self.token})
            if result:
                hosts = [x for x in result.values()
                         if x['.type'] == 'host' and
                         'mac' in x and 'name' in x]
                mac2name_list = [
                    (x['mac'].upper(), x['name']) for x in hosts]
                self.mac2name = dict(mac2name_list)
            else:
                # Error, handled in the _req_json_rpc
                return
        return self.mac2name.get(device.upper(), None)

    def _update_info(self):
        """Ensure the information from the Luci router is up to date.

        Returns boolean if scanning successful.
        """
        if not self.success_init:
            return False

        _LOGGER.info("Checking ARP")

        sys_url = '{}/cgi-bin/luci/rpc/sys'.format(self.origin)
        ip_url = '{}/cgi-bin/luci/rpc/ip'.format(self.origin)

        try:
            if self.use_ip_neighbors_table:
                # Newer OpenWRT releases (18.06+)
                result = _req_json_rpc(
                    ip_url, 'neighbors', {"family": 4},
                    params={'auth': self.token})
            else:
                try:
                    # Older OpenWRT releases (pre-18.06)
                    result = _req_json_rpc(
                        sys_url, 'net.arptable', params={
                            'auth': self.token})
                except LuciRpcMethodNotFoundError:
                    # This is normal for newer OpenWRT (18.06+)
                    _LOGGER.error('method net.arptable not found. '
                                  'Will try ip neighbors instead')
                    self.use_ip_neighbors_table = True
                    self._update_info()
                    return False
        except InvalidLuciTokenError:
            _LOGGER.info("Refreshing token")
            self.refresh_token()
            return False

        if result:
            self.last_results = []
            for device_entry in result:
                _LOGGER.debug('device_entry. %s', device_entry)

                if "Flags" in device_entry:
                    # Older OpenWRT releases (pre-18.06)
                    #
                    # Check if the Flags for each device contain
                    # NUD_REACHABLE and if so, add it to last_results
                    if device_entry['Flags'] == "0x2":
                        self.last_results.append(device_entry['HW address'])
                elif "mac" in device_entry:
                    # Newer OpenWRT releases (18.06+)
                    #
                    # Do not use `reachable` or `stale` values
                    # as they flap constantly even
                    # when the device is inside the network.
                    # The very existence of the mac in the results
                    # is enough to determine the "device is home"
                    self.last_results.append(device_entry['mac'])

            return True

        return False


def _req_json_rpc(url, method, *args, **kwargs):
    """Perform one JSON RPC operation."""
    data = json.dumps({'method': method, 'params': args})

    try:
        res = requests.post(url, data=data, timeout=5, **kwargs)
    except requests.exceptions.Timeout:
        _LOGGER.exception("Connection to the router timed out")
        return
    if res.status_code == 200:
        try:
            result = res.json()
        except ValueError:
            # If json decoder could not parse the response
            _LOGGER.exception("Failed to parse response from luci")
            return
        try:
            result_value = result['result']

            if result_value is not None:
                return result_value

            # On 18.06, we want to check for error 'Method not Found'
            error_message = result['error']['message']
            error_code = result['error']['code']
            _LOGGER.error(
                "method: '%s' returned an "
                "error '%s' (code: '%s).",
                method, error_message, error_code)
            if error_code == -32601:
                raise LuciRpcMethodNotFoundError
        except KeyError:
            _LOGGER.exception("No result in response from luci")
            return
    elif res.status_code == 401:
        # Authentication error
        _LOGGER.exception(
            "Failed to authenticate, check your username and password")
        return
    elif res.status_code == 403:
        _LOGGER.error("Luci responded with a 403 Invalid token")
        raise InvalidLuciTokenError

    else:
        _LOGGER.error("Invalid response from luci: %s", res)


def _get_token(origin, username, password):
    """Get authentication token for the given configuration."""
    url = '{}/cgi-bin/luci/rpc/auth'.format(origin)
    return _req_json_rpc(url, 'login', username, password)
