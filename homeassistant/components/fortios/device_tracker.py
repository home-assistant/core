"""
Support to use FortiOS device like FortiGate as device tracker.

This component is part of the device_tracker platform.
"""
import logging

from fortiosapi import FortiOSAPI
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
DEFAULT_VERIFY_SSL = False


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def get_scanner(hass, config):
    """Validate the configuration and return a FortiOSDeviceScanner."""
    host = config[DOMAIN][CONF_HOST]
    verify_ssl = config[DOMAIN][CONF_VERIFY_SSL]
    token = config[DOMAIN][CONF_TOKEN]

    fgt = FortiOSAPI()

    try:
        fgt.tokenlogin(host, token, verify_ssl)
    except ConnectionError as ex:
        _LOGGER.error("ConnectionError to FortiOS API: %s", ex)
        return None
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("Failed to login to FortiOS API: %s", ex)
        return None

    return FortiOSDeviceScanner(fgt)


class FortiOSDeviceScanner(DeviceScanner):
    """This class queries a FortiOS unit for connected devices."""

    def __init__(self, fgt) -> None:
        """Initialize the scanner."""
        self._clients = {}
        self._clients_json = {}
        self._fgt = fgt

    def update(self):
        """Update clients from the device."""
        clients_json = self._fgt.monitor("user/device/select", "")
        self._clients_json = clients_json

        self._clients = []

        if clients_json:
            for client in clients_json["results"]:
                if client["last_seen"] < 180:
                    self._clients.append(client["mac"].upper())

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self.update()
        return self._clients

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        _LOGGER.debug("Getting name of device %s", device)

        device = device.lower()

        data = self._clients_json

        if data == 0:
            _LOGGER.error("No json results to get device names")
            return None

        for client in data["results"]:
            if client["mac"] == device:
                try:
                    name = client["host"]["name"]
                    _LOGGER.debug("Getting device name=%s", name)
                    return name
                except KeyError as kex:
                    _LOGGER.error("Name not found in client data: %s", kex)
                    return None

        return None
