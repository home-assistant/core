"""
Support for the Tuya light.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.tuya/
"""

import asyncio
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_COLOR, Light)

from homeassistant.components.tuya import DOMAIN, DATA_TUYA, TuyaDevice
from homeassistant.util import color as colorutil

DEPENDENCIES = ['tuya']

DEVICE_TYPE = 'light'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tuya light platform."""
    tuya = hass.data[DATA_TUYA]
    devices = tuya.get_devices_by_type(DEVICE_TYPE)

    if DEVICE_TYPE not in hass.data[DOMAIN]['entities']:
        hass.data[DOMAIN]['entities'][DEVICE_TYPE] = []

    for device in devices:
        if device.object_id() not in hass.data[DOMAIN]['dev_ids']:
            add_devices([TuyaLight(device, hass)])
            hass.data[DOMAIN]['dev_ids'].append(device.object_id())


class TuyaLight(TuyaDevice, Light):
    """Tuya light device."""

    def __init__(self, tuya, hass):
        """Init Tuya light device."""
        super(TuyaLight, self).__init__(tuya, hass)
        self.entity_id = DEVICE_TYPE + '.' + tuya.object_id()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities'][DEVICE_TYPE].append(self)

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self.tuya.brightness()

    @property
    def hs_color(self):
        """Return the hs_color of the light."""
        return self.tuya.hs_color()

    @property
    def color_temp(self):
        """Return the color_temp of the light."""
        color_temp = self.tuya.color_temp()
        if color_temp is None:
            return None
        return colorutil.color_temperature_kelvin_to_mired(color_temp)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.tuya.state()

    @property
    def min_mireds(self):
        """Return color temperature min mireds."""
        return colorutil.color_temperature_kelvin_to_mired(
            self.tuya.min_color_temp())

    @property
    def max_mireds(self):
        """Return color temperature max mireds."""
        return colorutil.color_temperature_kelvin_to_mired(
            self.tuya.max_color_temp())

    def turn_on(self, **kwargs):
        """Turn on or control the light."""
        params = {}
        if ATTR_BRIGHTNESS in kwargs:
            params['brightness'] = kwargs[ATTR_BRIGHTNESS]
        if ATTR_HS_COLOR in kwargs:
            params['color'] = kwargs[ATTR_HS_COLOR]
        if ATTR_COLOR_TEMP in kwargs:
            params['color_temp'] = colorutil.color_temperature_mired_to_kelvin(
                    kwargs[ATTR_COLOR_TEMP])
        self.tuya.device_control(True, **params)
        self.schedule_update_ha_state(True)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self.tuya.device_control(False)

    @property
    def supported_features(self):
        """Flag supported features."""
        supports = SUPPORT_BRIGHTNESS
        if self.tuya.support_color():
            supports = supports | SUPPORT_COLOR
        if self.tuya.support_color_temp():
            supports = supports | SUPPORT_COLOR_TEMP
        return supports
