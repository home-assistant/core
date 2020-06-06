"""Support for the Elgato Avea lights."""
import logging

import avea

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.device_registry as dr
import homeassistant.util.color as color_util

from .const import DOMAIN as AVEA_DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORT_AVEA = SUPPORT_BRIGHTNESS | SUPPORT_COLOR


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Avea Light from a config entry."""
    lights = await hass.async_add_executor_job(discovery, hass)
    entities = []

    for light in lights:
        entities.append(AveaLight(light))

    async_add_entities(entities, True)
    return True


def discovery(hass):
    """Scan for Avea lightbulbs."""
    lights = []
    try:
        nearby_bulbs = avea.discover_avea_bulbs()
        for bulb in nearby_bulbs:
            bulb.get_name()
            bulb.get_brightness()
            if bulb.name != 'Unknown':
                lights.append(bulb)
            else:
                _LOGGER.warning("Found Avea bulb but could got get the name: %s", vars(bulb))
    except OSError as err:
        raise PlatformNotReady from err
    return lights


class AveaLight(LightEntity):
    """Representation of an Avea."""

    def __init__(self, light):
        """Initialize an AveaLight."""
        self._light = light
        self._mac = light.addr
        self._name = light.name
        self._state = None
        self._brightness = light.brightness

    @property
    def device_info(self):
        """Return information about the device."""
        info = {
            "identifiers": {(AVEA_DOMAIN, self.unique_id)},
            "name": self._name,
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._mac)},
            "manufacturer": "Elgato",
            "model": "Avea",
        }

        return info

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_AVEA

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._mac

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name
 
    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        if not kwargs:
            self._light.set_brightness(4095)
        else:
            if ATTR_BRIGHTNESS in kwargs:
                bright = round((kwargs[ATTR_BRIGHTNESS] / 255) * 4095)
                self._light.set_brightness(bright)
            if ATTR_HS_COLOR in kwargs:
                rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
                self._light.set_rgb(rgb[0], rgb[1], rgb[2])

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.set_brightness(0)

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        brightness = self._light.get_brightness()
        if brightness is not None:
            if brightness == 0:
                self._state = False
            else:
                self._state = True
            self._brightness = round(255 * (brightness / 4095))
