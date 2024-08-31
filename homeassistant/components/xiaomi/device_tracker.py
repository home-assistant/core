"""Support for Xiaomi Mi routers."""

from __future__ import annotations

from http import HTTPStatus
import logging

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME, default="admin"): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def get_scanner(hass: HomeAssistant, config: ConfigType) -> XiaomiDeviceScanner | None:
    """Validate the configuration and return a Xiaomi Device Scanner."""
    scanner = XiaomiDeviceScanner(config[DOMAIN])

    return scanner if scanner.success_init else None


class XiaomiDeviceScanner(DeviceScanner):
    """Class which queries a Xiaomi Mi router.

    Adapted from Luci scanner.
    """

    def __init__(self, config):
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.last_results = {}
        self.token = _get_token(self.host, self.username, self.password)

        self.mac2name = None
        self.success_init = self.token is not None

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()
        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        if self.mac2name is None:
            result = self._retrieve_list_with_retry()
            if result:
                hosts = [x for x in result if "mac" in x and "name" in x]
                mac2name_list = [(x["mac"].upper(), x["name"]) for x in hosts]
                self.mac2name = dict(mac2name_list)
            else:
                # Error, handled in the _retrieve_list_with_retry
                return None
        return self.mac2name.get(device.upper(), None)

    def _update_info(self):
        """Ensure the information from the router are up to date.

        Returns true if scanning successful.
        """
        if not self.success_init:
            return False

        result = self._retrieve_list_with_retry()
        if result:
            self._store_result(result)
            return True
        return False

    def _retrieve_list_with_retry(self):
        """Retrieve the device list with a retry if token is invalid.

        Return the list if successful.
        """
        _LOGGER.debug("Refreshing device list")
        result = _retrieve_list(self.host, self.token)
        if result:
            return result

        _LOGGER.debug("Refreshing token and retrying device list refresh")
        self.token = _get_token(self.host, self.username, self.password)
        return _retrieve_list(self.host, self.token)

    def _store_result(self, result):
        """Extract and store the device list in self.last_results."""
        self.last_results = []
        for device_entry in result:
            # Check if the device is marked as connected
            if int(device_entry["online"]) == 1:
                self.last_results.append(device_entry["mac"])


def _retrieve_list(host, token, **kwargs):
    """Get device list for the given host."""
    url = "http://{}/cgi-bin/luci/;stok={}/api/misystem/devicelist"
    url = url.format(host, token)
    try:
        res = requests.get(url, timeout=10, **kwargs)
    except requests.exceptions.Timeout:
        _LOGGER.exception("Connection to the router timed out at URL %s", url)
        return None
    if res.status_code != HTTPStatus.OK:
        _LOGGER.exception("Connection failed with http code %s", res.status_code)
        return None
    try:
        result = res.json()
    except ValueError:
        # If json decoder could not parse the response
        _LOGGER.exception("Failed to parse response from mi router")
        return None
    try:
        xiaomi_code = result["code"]
    except KeyError:
        _LOGGER.exception("No field code in response from mi router. %s", result)
        return None
    if xiaomi_code == 0:
        try:
            return result["list"]
        except KeyError:
            _LOGGER.exception("No list in response from mi router. %s", result)
            return None
    else:
        _LOGGER.info(
            "Receive wrong Xiaomi code %s, expected 0 in response %s",
            xiaomi_code,
            result,
        )
        return None


def _get_token(host, username, password):
    """Get authentication token for the given host+username+password."""
    url = f"http://{host}/cgi-bin/luci/api/xqsystem/login"
    data = {"username": username, "password": password}
    try:
        res = requests.post(url, data=data, timeout=5)
    except requests.exceptions.Timeout:
        _LOGGER.exception("Connection to the router timed out")
        return None
    if res.status_code == HTTPStatus.OK:
        try:
            result = res.json()
        except ValueError:
            # If JSON decoder could not parse the response
            _LOGGER.exception("Failed to parse response from mi router")
            return None
        try:
            return result["token"]
        except KeyError:
            error_message = (
                "Xiaomi token cannot be refreshed, response from "
                "url: [%s] \nwith parameter: [%s] \nwas: [%s]"
            )
            _LOGGER.exception(error_message, url, data, result)
            return None

    _LOGGER.error("Invalid response: [%s] at url: [%s] with data [%s]", res, url, data)
    return None
