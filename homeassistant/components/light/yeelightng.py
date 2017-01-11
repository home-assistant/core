"""
Support for Xiaomi Yeelight Wifi color bulb.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.yeelight/
"""
import logging
import socket

import voluptuous as vol

from homeassistant.util.color import color_temperature_mired_to_kelvin
from homeassistant.const import CONF_DEVICES, CONF_NAME, STATE_OFF
from homeassistant.components.light import (ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_TRANSITION,
                                            ATTR_COLOR_TEMP, ATTR_WHITE_VALUE,
                                            SUPPORT_BRIGHTNESS, SUPPORT_RGB_COLOR, SUPPORT_TRANSITION,
                                            SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_WHITE_VALUE,
                                            Light, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['yeelight==0.0.12']

_LOGGER = logging.getLogger(__name__)

CONF_TRANSITION = "transition"
DEFAULT_TRANSITION=10

DOMAIN = 'yeelightng'

DEVICE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME): cv.string,
                            vol.Optional(CONF_TRANSITION, default=DEFAULT_TRANSITION): cv.positive_int})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}, })

COLOR_SUPPORTS = (SUPPORT_BRIGHTNESS |
                  SUPPORT_RGB_COLOR |
                  SUPPORT_TRANSITION |
                  SUPPORT_COLOR_TEMP |
                  SUPPORT_EFFECT |
                  SUPPORT_WHITE_VALUE)

MONO_SUPPORTS = (SUPPORT_BRIGHTNESS |
                 SUPPORT_TRANSITION)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Yeelight bulbs."""
    lights = []
    if discovery_info is not None:
        device = {'name': discovery_info['hostname'],
                  'ipaddr': discovery_info['host']}
        _LOGGER.error("Adding autodetected %s", discovery_info['hostname'])
        lights.append(YeelightLight(device, {'transition': DEFAULT_TRANSITION}))
    else:
        for ipaddr, device_config in config[CONF_DEVICES].items():
            device = {'name': device_config[CONF_NAME], 'ipaddr': ipaddr}
            _LOGGER.error("Adding configured %s", device_config[CONF_NAME])
            lights.append(YeelightLight(device, device_config))

    add_devices(lights)


class YeelightLight(Light):
    """Representation of a Yeelight light."""

    def __init__(self, device, config):
        """Initialize the light."""
        import yeelight

        self._name = device['name']
        self._ipaddr = device['ipaddr']
        self.config = config
        self._supported_features = None
        self.__bulb = None
        self.__properties = None

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return "{}.{}".format(self.__class__, self._ipaddr)

    @property
    def color_temp(self):
        return self._properties.get("color_temp", None)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        if self._properties.get("power", STATE_OFF) == STATE_OFF:
            return False
        return True

    @property
    def brightness(self):
        """Return the brightness of this light between 1..255."""
        bright = self._properties.get("bright", None)
        if bright:
            return 255 * (int(bright) / 100)

        return None

    @property
    def rgb_color(self):
        """Return the color property."""
        rgb = self._properties.get("rgb", None)
        if rgb is None:
            return None

        rgb = int(rgb)

        b = rgb & 255
        g = (rgb >> 8) & 255
        r = (rgb >> 16) & 25

        return r, g, b

    @property
    def effect_list(self):
        return ["Loopy"]

    @property
    def effect(self):
        return "wat"

    @property
    def _properties(self):
        return self._bulb.last_properties

    @property
    def _bulb(self):
        import yeelight
        if self.__bulb is None:
            try:
                self.__bulb = yeelight.Bulb(self._ipaddr)

                self.__bulb.get_properties()  # force init for type
                btype = self.__bulb.bulb_type
                if btype == yeelight.BulbType.Color:
                    self._supported_features = COLOR_SUPPORTS
                elif btype == yeelight.BulbType.White:
                    self._supported_features = MONO_SUPPORTS
                else:
                    raise Exception("Got unknown bulb type %s" % btype)
            except yeelight.BulbException as ex:
                _LOGGER.error("Got error from bulb %s, %s: %s", self._ipaddr,
                              self._name, ex)
            except socket.error as ex:
                _LOGGER.error("Failed to connect to bulb %s, %s: %s", self._ipaddr,
                              self._name, ex)
            except Exception as ex:
                _LOGGER.error("Non socket.error exception from bulb: %s", ex)

        return self.__bulb

    def update(self):
        self._bulb.get_properties()

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        _LOGGER.error("ON %s", kwargs)

        # white bulb has problems with duration > 9000, doesn't always start..
        # move this to python-yeelight

        duration = min(kwargs.get(ATTR_TRANSITION, self.config["transition"]) * 100, 900)

        if self.supported_features & SUPPORT_COLOR_TEMP:
            try:
                colortemp = kwargs.get(ATTR_COLOR_TEMP)
                if colortemp:
                    temp_in_k = color_temperature_mired_to_kelvin(colortemp)
                    _LOGGER.error("Changing color temp to %s K", temp_in_k)
                    self._bulb.set_color_temp(temp_in_k, duration=duration)
            except Exception as ex:
                _LOGGER.error("Got exception when setting the color temp: %s", ex)

        if self.supported_features & SUPPORT_RGB_COLOR:
            try:
                rgb = kwargs.get(ATTR_RGB_COLOR)
                if rgb:
                    self._bulb.set_rgb(rgb[0], rgb[1], rgb[2], duration=duration)
            except Exception as ex:
                _LOGGER.error("Got exception when setting the RGB: %s", ex)

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness:
            self._bulb.set_brightness(brightness / 255 * 100, duration=duration)

        self._bulb.turn_on(duration=duration)

        try:
            self._bulb.set_default()
        except Exception:
            pass  # bulb returns error sometimes on set_default


    def turn_off(self, **kwargs):
        """Turn off."""
        _LOGGER.error("OFF: %s", kwargs)
        self._bulb.turn_off()
