"""
homeassistant.components.light.osramlightify
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Osram Lightify platform that implements lights. Largely built off the demo
example.
Uses: https://github.com/aneumeier/python-lightify for the Osram light interface.

Todo:
Need to add support for Non RGBW lights.
Need to add polling support (If lights are switched on from Android App etc).

"""

import logging
from datetime import timedelta

from homeassistant import util
from homeassistant.const import CONF_HOST
from homeassistant.components.light import (
    Light,
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR
)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['lightify==1.0.3']

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return lights. """
    import lightify
    host = config.get(CONF_HOST)
    if host:
        try:
            bridge = lightify.Lightify(host)
        except Exception as e:
            msg = 'Error connecting to bridge at: {} due to: {}'.format(host,
                                                                        str(e))
            _LOGGER.exception(msg)
            return False
        setup_bridge(bridge, add_devices_callback)
    else:
        _LOGGER.error('No host found in configuration')
        return False


def setup_bridge(bridge, add_devices_callback):
    """ Setup the Lightify bridge """
    lights = {}

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_lights():
        """ Update the lights objects with latest info from bridge"""
        bridge.update_all_light_status()

        new_lights = []

        for (light_id, light) in bridge.lights().items():
            if light_id not in lights:
                osram_light = OsramLightifyLight(light_id, light,
                                                 update_lights)

                lights[light_id] = osram_light
                new_lights.append(osram_light)
            else:
                lights[light_id].light = light

        if new_lights:
            add_devices_callback(new_lights)

    update_lights()


class OsramLightifyLight(Light):
    """ Defines an Osram Lightify Light """
    def __init__(self, light_id, light, update_lights):
        self._light = light
        self._light_id = light_id
        self.update_lights = update_lights

    @property
    def name(self):
        """ Returns the name of the device if any. """
        return self._light.name()

    @property
    def rgb_color(self):
        """ Last RGB color value set. """
        return self._light.rgb()

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return (self._light.lum() * 2.55)

    @property
    def is_on(self):
        """ Update Status to True if device is on. """
        self.update_lights()
        _LOGGER.debug("is_on light state for light: %s is: %s " %
                      (self._light.name(), self._light.on()))
        return self._light.on()

    def turn_on(self, **kwargs):
        """ Turn the device on. """
        self._light.set_onoff(1)

        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            self._light.set_rgb(r, g, b, 0)

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            self._light.set_luminance(int(brightness / 2.55), 0)
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the device off. """
        self._light.set_onoff(0)
        self.update_ha_state()

    def update(self):
        """Synchronize state with bridge."""
        self.update_lights(no_throttle=True)
