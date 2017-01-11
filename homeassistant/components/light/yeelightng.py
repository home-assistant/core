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
                                            ATTR_COLOR_TEMP, ATTR_FLASH, FLASH_SHORT, FLASH_LONG,
                                            SUPPORT_BRIGHTNESS, SUPPORT_RGB_COLOR, SUPPORT_TRANSITION,
                                            SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_FLASH, SUPPORT_XY_COLOR,
                                            Light, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['yeelight==0.0.13']

_LOGGER = logging.getLogger(__name__)

CONF_TRANSITION = "transition"
DEFAULT_TRANSITION=350

DOMAIN = 'yeelightng'

DEVICE_SCHEMA = vol.Schema({vol.Optional(CONF_NAME): cv.string,
                            vol.Optional(CONF_TRANSITION, default=DEFAULT_TRANSITION): cv.positive_int})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}, })

COLOR_SUPPORTS = (SUPPORT_RGB_COLOR |
                  SUPPORT_COLOR_TEMP |
                  SUPPORT_XY_COLOR)

SUPPORTS = (SUPPORT_BRIGHTNESS |
            SUPPORT_TRANSITION |
            SUPPORT_EFFECT |
            SUPPORT_FLASH)

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
        self._supported_features = SUPPORTS
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
        return []

    @property
    def effect(self):
        return "NONE"

    @property
    def _properties(self):
        return self._bulb.last_properties

    @property
    def _bulb(self):
        import yeelight
        self._module = yeelight
        if self.__bulb is None:
            try:
                self.__bulb = yeelight.Bulb(self._ipaddr)

                self.__bulb.get_properties()  # force init for type
                btype = self.__bulb.bulb_type
                if btype == yeelight.BulbType.Color:
                    self._supported_features += COLOR_SUPPORTS
            except (yeelight.BulbException, socket.error) as ex:
                _LOGGER.error("Failed to connect to bulb %s, %s: %s", self._ipaddr,
                              self._name, ex)
            except Exception as ex:
                _LOGGER.error("Non socket.error exception from bulb: %s", ex)

        return self.__bulb

    def update(self):
        self._bulb.get_properties()

    def cmd(func):
        def wrap(self, *args, **kwargs):
            try:
                #_LOGGER.debug("Calling %s with %s %s" % (func, args, kwargs))
                return func(self, *args, **kwargs)
            except self._module.BulbException as ex:
                _LOGGER.error("Error when calling %s: %s", func, ex)
        return wrap

    @cmd
    def set_brightness(self, brightness, duration):
        if brightness:
            self._bulb.set_brightness(brightness / 255 * 100, duration=duration)

    @cmd
    def set_rgb(self, rgb, duration):
        if rgb and self.supported_features & SUPPORT_RGB_COLOR:
            self._bulb.set_rgb(rgb[0], rgb[1], rgb[2], duration=duration)

    @cmd
    def set_colortemp(self, colortemp, duration):
        if colortemp and self.supported_features & SUPPORT_COLOR_TEMP:
            temp_in_k = color_temperature_mired_to_kelvin(colortemp)
            self._bulb.set_color_temp(temp_in_k, duraation=duration)
            _LOGGER.error("Changing color temp to %s K", temp_in_k)

    @cmd
    def set_default(self):
        self._bulb.set_default()

    @cmd
    def set_flash(self, flash):
        if flash:  # to be refined..
            _LOGGER.error("Got flash! %s" % flash)
            # example taken from python-yeelight's quick pulse
            transitions = [self._module.HSVTransition(hue, 100, duration=500)
                          for hue in range(0, 359, 40)]

            if flash == FLASH_LONG:
                flow = self._module.Flow(count=50, transitions=transitions)
            elif flash == FLASH_SHORT:
                flow = self._module.Flow(count=50, transitions=transitions)
            else:
                _LOGGER.error("Unknown flash type: %s", flash)

            self._bulb.bulb.start_flow(flow)

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        colortemp = kwargs.get(ATTR_COLOR_TEMP)
        rgb = kwargs.get(ATTR_RGB_COLOR)
        flash = kwargs.get(ATTR_FLASH)

        # white bulb has problems with duration > 9000, doesn't always start..
        # move this to python-yeelight

        duration = min(kwargs.get(ATTR_TRANSITION, self.config["transition"]), 9000)

        self._bulb.turn_on(duration=duration)

        # values checked for none in methods
        self.set_rgb(rgb, duration)
        self.set_colortemp(colortemp, duration)
        self.set_brightness(brightness, duration)
        self.set_flash(flash)
        self.set_default()  # saving current settings to the bulb

    def turn_off(self, **kwargs):
        """Turn off."""
        self._bulb.turn_off()
