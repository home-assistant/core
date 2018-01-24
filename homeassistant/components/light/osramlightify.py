"""
Support for Osram Lightify.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.osramlightify/
"""
from datetime import timedelta
import logging
import random
import socket

import voluptuous as vol

from homeassistant import util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_EFFECT, ATTR_RGB_COLOR,
    ATTR_TRANSITION, ATTR_XY_COLOR, EFFECT_RANDOM, PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_EFFECT, SUPPORT_RGB_COLOR,
    SUPPORT_TRANSITION, SUPPORT_XY_COLOR, Light)
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired, color_temperature_mired_to_kelvin,
    color_xy_brightness_to_RGB)

REQUIREMENTS = ['lightify==1.0.6.1']

_LOGGER = logging.getLogger(__name__)

CONF_ALLOW_LIGHTIFY_GROUPS = 'allow_lightify_groups'

DEFAULT_ALLOW_LIGHTIFY_GROUPS = True

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SUPPORT_OSRAMLIGHTIFY = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP |
                         SUPPORT_EFFECT | SUPPORT_RGB_COLOR |
                         SUPPORT_TRANSITION | SUPPORT_XY_COLOR)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_ALLOW_LIGHTIFY_GROUPS,
                 default=DEFAULT_ALLOW_LIGHTIFY_GROUPS): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Osram Lightify lights."""
    import lightify

    host = config.get(CONF_HOST)
    add_groups = config.get(CONF_ALLOW_LIGHTIFY_GROUPS)

    try:
        bridge = lightify.Lightify(host)
    except socket.error as err:
        msg = "Error connecting to bridge: {} due to: {}".format(
            host, str(err))
        _LOGGER.exception(msg)
        return

    setup_bridge(bridge, add_devices, add_groups)


def setup_bridge(bridge, add_devices, add_groups):
    """Set up the Lightify bridge."""
    lights = {}

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_lights():
        """Update the lights objects with latest info from bridge."""
        try:
            bridge.update_all_light_status()
            bridge.update_group_list()
        except TimeoutError:
            _LOGGER.error("Timeout during updating of lights")
        except OSError:
            _LOGGER.error("OSError during updating of lights")

        new_lights = []

        for (light_id, light) in bridge.lights().items():
            if light_id not in lights:
                osram_light = OsramLightifyLight(
                    light_id, light, update_lights)
                lights[light_id] = osram_light
                new_lights.append(osram_light)
            else:
                lights[light_id].light = light

        if add_groups:
            for (group_name, group) in bridge.groups().items():
                if group_name not in lights:
                    osram_group = OsramLightifyGroup(
                        group, bridge, update_lights)
                    lights[group_name] = osram_group
                    new_lights.append(osram_group)
                else:
                    lights[group_name].group = group

        if new_lights:
            add_devices(new_lights)

    update_lights()


class Luminary(Light):
    """Representation of Luminary Lights and Groups."""

    def __init__(self, luminary, update_lights):
        """Initialize a Luminary light."""
        self.update_lights = update_lights
        self._luminary = luminary
        self._brightness = None
        self._rgb = [None]
        self._name = None
        self._temperature = None
        self._state = False
        self.update()

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def rgb_color(self):
        """Last RGB color value set."""
        return self._rgb

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._temperature

    @property
    def brightness(self):
        """Brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self):
        """Update status to True if device is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OSRAMLIGHTIFY

    @property
    def effect_list(self):
        """List of supported effects."""
        return [EFFECT_RANDOM]

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION] * 10)
            _LOGGER.debug("turn_on requested transition time for light: "
                          "%s is: %s", self._name, transition)
        else:
            transition = 0
            _LOGGER.debug("turn_on requested transition time for light: "
                          "%s is: %s", self._name, transition)

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]
            _LOGGER.debug("turn_on requested brightness for light: %s is: %s ",
                          self._name, self._brightness)
            self._luminary.set_luminance(
                int(self._brightness / 2.55), transition)
        else:
            self._luminary.set_onoff(1)

        if ATTR_RGB_COLOR in kwargs:
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            _LOGGER.debug("turn_on requested ATTR_RGB_COLOR for light:"
                          " %s is: %s %s %s ",
                          self._name, red, green, blue)
            self._luminary.set_rgb(red, green, blue, transition)

        if ATTR_XY_COLOR in kwargs:
            x_mired, y_mired = kwargs[ATTR_XY_COLOR]
            _LOGGER.debug("turn_on requested ATTR_XY_COLOR for light:"
                          " %s is: %s,%s", self._name, x_mired, y_mired)
            red, green, blue = color_xy_brightness_to_RGB(
                x_mired, y_mired, self._brightness)
            self._luminary.set_rgb(red, green, blue, transition)

        if ATTR_COLOR_TEMP in kwargs:
            color_t = kwargs[ATTR_COLOR_TEMP]
            kelvin = int(color_temperature_mired_to_kelvin(color_t))
            _LOGGER.debug("turn_on requested set_temperature for light: "
                          "%s: %s", self._name, kelvin)
            self._luminary.set_temperature(kelvin, transition)

        if ATTR_EFFECT in kwargs:
            effect = kwargs.get(ATTR_EFFECT)
            if effect == EFFECT_RANDOM:
                self._luminary.set_rgb(
                    random.randrange(0, 255), random.randrange(0, 255),
                    random.randrange(0, 255), transition)
                _LOGGER.debug("turn_on requested random effect for light: "
                              "%s with transition %s", self._name, transition)

        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        _LOGGER.debug("Attempting to turn off light: %s", self._name)
        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION] * 10)
            _LOGGER.debug("turn_off requested transition time for light:"
                          " %s is: %s ", self._name, transition)
            self._luminary.set_luminance(0, transition)
        else:
            transition = 0
            _LOGGER.debug("turn_off requested transition time for light:"
                          " %s is: %s ", self._name, transition)
        self._luminary.set_onoff(0)
        self.schedule_update_ha_state()

    def update(self):
        """Synchronize state with bridge."""
        self.update_lights(no_throttle=True)
        self._name = self._luminary.name()


class OsramLightifyLight(Luminary):
    """Representation of an Osram Lightify Light."""

    def __init__(self, light_id, light, update_lights):
        """Initialize the Lightify light."""
        self._light_id = light_id
        super().__init__(light, update_lights)

    def update(self):
        """Update status of a light."""
        super().update()
        self._state = self._luminary.on()
        self._rgb = self._luminary.rgb()
        o_temp = self._luminary.temp()
        if o_temp == 0:
            self._temperature = None
        else:
            self._temperature = color_temperature_kelvin_to_mired(
                self._luminary.temp())
        self._brightness = int(self._luminary.lum() * 2.55)


class OsramLightifyGroup(Luminary):
    """Representation of an Osram Lightify Group."""

    def __init__(self, group, bridge, update_lights):
        """Initialize the Lightify light group."""
        self._bridge = bridge
        self._light_ids = []
        super().__init__(group, update_lights)

    def _get_state(self):
        """Get state of group."""
        lights = self._bridge.lights()
        return any(lights[light_id].on() for light_id in self._light_ids)

    def update(self):
        """Update group status."""
        super().update()
        self._light_ids = self._luminary.lights()
        light = self._bridge.lights()[self._light_ids[0]]
        self._brightness = int(light.lum() * 2.55)
        self._rgb = light.rgb()
        o_temp = light.temp()
        if o_temp == 0:
            self._temperature = None
        else:
            self._temperature = color_temperature_kelvin_to_mired(o_temp)
        self._state = light.on()
