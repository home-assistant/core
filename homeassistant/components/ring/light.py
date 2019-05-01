"""
This component provides support to the Ring Floodlight Camera lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.ring/
"""
import asyncio
import logging

from datetime import timedelta

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from . import (
    ATTRIBUTION, DEFAULT_ENTITY_NAMESPACE, DATA_RING)
from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR_TEMP, SUPPORT_COLOR, SUPPORT_TRANSITION)
from homeassistant.const import ATTR_ATTRIBUTION, CONF_SCAN_INTERVAL
from homeassistant.util import dt as dt_util


DEPENDENCIES = ['ring']

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a StickUp Camera light."""
    ring = hass.data[DATA_RING]

    lights = []
    for camera in ring.stickup_cams:
        if camera.lights:
            lights.append(RingLight(camera))

    add_entities(lights, True)
    return True


class RingLight(Light):
    """An implementation of a Ring camera light."""

    def __init__(self, ringLight):
        """Initialize a Ring Light.

        Default brightness and white color.
        """
        self._ringLight = ringLight

    @property
    def name(self):
        """Return the display name of this light."""
        return self._ringLight.name

    @property
    def brightness(self):
        """Read back the brightness of the light.

        Returns integer in the range of 1-255.
        """
        return self._brightness

    @property
    def hs_color(self):
        """Read back the color of the light."""
        return self._hs_color

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._is_on

    @property
    def should_poll(self):
        """Return if we should poll this device."""
        return False

    @property
    def assumed_state(self) -> bool:
        """Return True if unable to access real state of the entity."""
        return False

    def turn_on(self, **kwargs):
        """Instruct the light to turn on"""
        self._ringLight.lights = "on"
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._ringLight.lights = "off"
        self._is_on = False
        self.schedule_update_ha_state()

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._ringLight.update()
        self._is_on = self._ringLight.lights == "on"