"""Support for EverLights lights."""
import logging
from datetime import timedelta
from typing import Tuple

import voluptuous as vol

from homeassistant.const import CONF_HOSTS
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, ATTR_EFFECT,
    SUPPORT_BRIGHTNESS, SUPPORT_EFFECT, SUPPORT_COLOR,
    Light, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

SUPPORT_EVERLIGHTS = (SUPPORT_EFFECT | SUPPORT_BRIGHTNESS | SUPPORT_COLOR)

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOSTS): vol.All(cv.ensure_list, [cv.string]),
})

NAME_FORMAT = "EverLights {} Zone {}"


def color_rgb_to_int(red: int, green: int, blue: int) -> int:
    """Return a RGB color as an integer."""
    return red*256*256+green*256+blue


def color_int_to_rgb(value: int) -> Tuple[int, int, int]:
    """Return an RGB tuple from an integer."""
    return (value >> 16, (value >> 8) & 0xff, value & 0xff)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the EverLights lights from configuration.yaml."""
    import pyeverlights
    lights = []

    for ipaddr in config[CONF_HOSTS]:
        api = pyeverlights.EverLights(ipaddr,
                                      async_get_clientsession(hass))

        try:
            status = await api.get_status()

            effects = await api.get_all_patterns()

        except pyeverlights.ConnectionError:
            raise PlatformNotReady

        else:
            lights.append(EverLightsLight(api, pyeverlights.ZONE_1,
                                          status, effects))
            lights.append(EverLightsLight(api, pyeverlights.ZONE_2,
                                          status, effects))

    async_add_entities(lights)


class EverLightsLight(Light):
    """Representation of a Flux light."""

    def __init__(self, api, channel, status, effects):
        """Initialize the light."""
        self._api = api
        self._channel = channel
        self._status = status
        self._effects = effects
        self._mac = status['mac']
        self._error_reported = False
        self._hs_color = [255, 255]
        self._brightness = 255
        self._effect = None
        self._available = True

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return '{}-{}'.format(self._mac, self._channel)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def name(self):
        """Return the name of the device."""
        return NAME_FORMAT.format(self._mac, self._channel)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._status['ch{}Active'.format(self._channel)] == 1

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs_color

    @property
    def effect(self):
        """Return the effect property."""
        return self._effect

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_EVERLIGHTS

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._effects

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        hs_color = kwargs.get(ATTR_HS_COLOR, self._hs_color)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
        effect = kwargs.get(ATTR_EFFECT)

        if effect is not None:
            colors = await self._api.set_pattern_by_id(self._channel, effect)

            rgb = color_int_to_rgb(colors[0])
            hsv = color_util.color_RGB_to_hsv(*rgb)
            hs_color = hsv[:2]
            brightness = hsv[2] / 100 * 255

        else:
            rgb = color_util.color_hsv_to_RGB(*hs_color, brightness/255*100)
            colors = [color_rgb_to_int(*rgb)]

            await self._api.set_pattern(self._channel, colors)

        self._hs_color = hs_color
        self._brightness = brightness
        self._effect = effect

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._api.clear_pattern(self._channel)

    async def async_update(self):
        """Synchronize state with control box."""
        import pyeverlights

        try:
            self._status = await self._api.get_status()
        except pyeverlights.ConnectionError:
            if self._available:
                _LOGGER.warning("EverLights control box connection lost.")
            self._available = False
        else:
            if not self._available:
                _LOGGER.warning("EverLights control box connection restored.")
            self._available = True
