"""
Support for the Opple light.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.opple/
"""

import logging

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, Light)
from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.util.color import \
    color_temperature_kelvin_to_mired as kelvin_to_mired
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin

REQUIREMENTS = ['pyoppleio==1.0.5']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default="opple light"): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Opple light platform."""
    name = config.get('name')
    host = config.get('host')
    add_devices([OppleLight(name, host)])


class OppleLight(Light):
    """Opple light device."""

    def __init__(self, name, host):
        from pyoppleio.OppleLightDevice import OppleLightDevice
        self._device = OppleLightDevice(host)

        self._name = name
        self._is_on = None
        self._brightness = None
        self._color_temp = None

        _LOGGER.debug("init light %s %s", self._device.ip, self._device.mac)

    @property
    def available(self):
        return self._device.is_online

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._is_on

    @property
    def brightness(self):
        return self._brightness

    @property
    def color_temp(self):
        return kelvin_to_mired(self._color_temp)

    @property
    def min_mireds(self):
        return 175

    @property
    def max_mireds(self):
        return 333

    @property
    def supported_features(self):
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

    def turn_on(self, **kwargs):
        _LOGGER.debug("Turn on light %s %s", self._device.ip, kwargs)
        if not self.is_on:
            self._is_on = self._device.power_on = True

        if ATTR_BRIGHTNESS in kwargs and \
                self.brightness != kwargs[ATTR_BRIGHTNESS]:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            self._device.brightness = kwargs[ATTR_BRIGHTNESS]

        if ATTR_COLOR_TEMP in kwargs and \
                self.brightness != kwargs[ATTR_COLOR_TEMP]:
            color_temp = mired_to_kelvin(kwargs[ATTR_COLOR_TEMP])
            self._color_temp = self._device.color_temperature = color_temp

    def turn_off(self, **kwargs):
        self._device.power_on = False
        _LOGGER.debug("Turn off light %s", self._device.ip)

    def update(self):
        self._device.update()
        self._is_on = self._device.power_on
        self._brightness = self._device.brightness
        self._color_temp = self._device.color_temperature

        if not self.available:
            _LOGGER.debug("Light %s is offline", self._device.ip)
        elif not self.is_on:
            _LOGGER.debug("Update light %s success: power off",
                          self._device.ip)
        else:
            _LOGGER.debug("Update light %s success: power on " +
                          "brightness %s color temperature %s",
                          self._device.ip, self._brightness, self._color_temp)
