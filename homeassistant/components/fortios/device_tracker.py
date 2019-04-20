"""
Support to use FortiOS device like FortiGate as device tracker.

This component is part of the device_tracker platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fortiosapi/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.const import CONF_VERIFY_SSL

REQUIREMENTS = ['fortiosapi==0.10.5']

_LOGGER = logging.getLogger(__name__)
DEFAULT_VERIFY_SSL = False


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean
})


def get_scanner(hass, config):
    """Validate the configuration and return a FortiOSDeviceScanner."""
    from fortiosapi import FortiOSAPI

    host = config[DOMAIN].get(CONF_HOST)
    verify_ssl = config[DOMAIN].get(CONF_VERIFY_SSL)
    token = config[DOMAIN].get(CONF_TOKEN)

    _LOGGER.debug("host : %s", host)
    _LOGGER.debug("verify_ssl : %s", verify_ssl)
    _LOGGER.debug("token : %s", token)

    _LOGGER.debug('fortios, get_scanner')

    fgt = FortiOSAPI()

    try:
        fgt.tokenlogin(host, token, verify_ssl)
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("Unable login to fgt Exception : %s", ex)

    try:
        scanner = FortiOSDeviceScanner(fgt)
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.error("FortiOS get_scanner Initialize failed: %s", ex)
        return False

    return scanner


class FortiOSDeviceScanner(DeviceScanner):
    """This class queries a FortiOS unit for connected devices."""

    def __init__(self, fgt) -> None:
        """Initialize the scanner."""
        _LOGGER.debug('__init__')
        self._clients = {}
        self._clients_json = {}
        self._fgt = fgt
        self._update()

    def _update(self):
        """Get the clients from the device."""
        """
        Ensure the information from the FortiOS is up to date.
        Retrieve data from FortiOS and return parsed result.
        """

        clients_json = self._fgt.monitor('user/device/select', '')
        self._clients_json = clients_json

        self._clients = []

        if clients_json:
            for client in clients_json['results']:
                if client['last_seen'] < 180:
                    self._clients.append(client['mac'].upper())

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update()
        return self._clients

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""

        _LOGGER.debug("get_device_name device=%s", device)

        device = device.lower()

        data = self._clients_json

        if data == 0:
            _LOGGER.error('get_device_name no json results')
            return None

        for client in data['results']:
            if client['mac'] == device:
                try:
                    name = client['host']['name']
                    _LOGGER.debug("get_device_name name=%s", name)
                    return name
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.error("No name found in clients_json: %s", ex)
                    return None

        return None
