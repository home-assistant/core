"""
Support to use FortiOS device like FortiGate as device tracker.

This component is part of the device_tracker platform.
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.const import CONF_VERIFY_SSL
from fortiosapi import FortiOSAPI

_LOGGER = logging.getLogger(__name__)
DEFAULT_VERIFY_SSL = False


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean
})


def get_scanner(hass, config):
    """Validate the configuration and return a FortiOSDeviceScanner."""

    host = config[DOMAIN].get(CONF_HOST)
    verify_ssl = config[DOMAIN].get(CONF_VERIFY_SSL)
    token = config[DOMAIN].get(CONF_TOKEN)

    _LOGGER.debug("host : %s", host)
    _LOGGER.debug("verify_ssl : %s", verify_ssl)

    fgt = FortiOSAPI()

    try:
        fgt.tokenlogin(host, token, verify_ssl)
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("Failed to login to FortiOS API")
        return None

    try:
        scanner = FortiOSDeviceScanner(fgt)
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("FortiOS get_scanner Initialize failed: %s", ex)
        return None

    return scanner


class FortiOSDeviceScanner(DeviceScanner):
    """This class queries a FortiOS unit for connected devices."""

    def __init__(self, fgt) -> None:
        """Initialize the scanner."""
        self._clients = {}
        self._clients_json = {}
        self._fgt = fgt

    def update(self):
        """Update clients from the device."""
        clients_json = (self._fgt.monitor('user/device/select',
                                          ''))  # pylint: disable=W0105
        self._clients_json = clients_json

        self._clients = []

        if clients_json:
            for client in clients_json['results']:
                if client['last_seen'] < 180:
                    self._clients.append(client['mac'].upper())

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
            _LOGGER.error('No json results to get device names')
            return None

        for client in data['results']:
            if client['mac'] == device:
                try:
                    name = client['host']['name']
                    _LOGGER.debug("Getting device name=%s", name)
                    return name
                except KeyError as kex:
                    _LOGGER.error("Name not found in client data: %s", kex)
                    return None

        return None
