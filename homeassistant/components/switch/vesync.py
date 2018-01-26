"""
Support for Etekcity Wifi Smart Switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.Vesync/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['vesync==1.0.1']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Etekcity Vesync Switch'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up Vesync switches."""
    from vesync.api import VesyncApi

    switches = []

    try:
        api = VesyncApi(config.get(CONF_USERNAME), config.get(CONF_PASSWORD))
        _LOGGER.debug("Connected to Vesync API")
    except RuntimeError:
        _LOGGER.error("Failed to connect to Vesync API")
        return False

    try:
        devices = api.get_devices()
        _LOGGER.debug("Retrieved devices from Vesync API")
    except RuntimeError:
        _LOGGER.error("Failed to retrieve devices from Vesync API")
        return False

    for switch in devices:
        switches.append(VesyncSwitch(switch, api))

    add_devices_callback(switches, True)


class VesyncSwitch(SwitchDevice):
    """Representation of an EtekCity Vesync switch."""

    def __init__(self, switch, api):
        """Initialize the Vesync device."""
        self._switch = switch
        self._api = api

    @property
    def name(self):
        """Return the name of the switch."""
        return self._switch["deviceName"]

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._switch["deviceStatus"] == "on"

    def update(self):
        """Update device state."""
        try:
            devices = self._api.get_devices()
            for device in devices:
                if (device["cid"] == self._switch["cid"]):
                    self._switch = device
                    break
        except RuntimeError:
            _LOGGER.error("Error while fetching Vesync state")

    def turn_on(self, **kwargs):
        """Turn the device on."""
        try:
            self._api.turn_on(self._switch["cid"])
        except RuntimeError:
            _LOGGER.error("Error while turning on Vesync")

    def turn_off(self, **kwargs):
        """Turn the device on."""
        try:
            self._api.turn_off(self._switch["cid"])
        except RuntimeError:
            _LOGGER.error("Error while turning off Vesync")
