"""Support for KNX/IP lights."""
from enum import Enum

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR, SUPPORT_COLOR_TEMP, Light)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

from . import ATTR_DISCOVER_DEVICES, DATA_KNX

CONF_STATE_ADDRESS = 'state_address'
CONF_BRIGHTNESS_ADDRESS = 'brightness_address'
CONF_BRIGHTNESS_STATE_ADDRESS = 'brightness_state_address'
CONF_COLOR_ADDRESS = 'color_address'
CONF_COLOR_STATE_ADDRESS = 'color_state_address'
CONF_COLOR_TEMP_ADDRESS = 'color_temperature_address'
CONF_COLOR_TEMP_STATE_ADDRESS = 'color_temperature_state_address'
CONF_COLOR_TEMP_MODE = 'color_temperature_mode'
CONF_MIN_KELVIN = 'min_kelvin'
CONF_MAX_KELVIN = 'max_kelvin'

DEFAULT_NAME = 'KNX Light'
DEFAULT_COLOR = [255, 255, 255]
DEFAULT_BRIGHTNESS = 255
DEFAULT_COLOR_TEMP_MODE = 'absolute'
DEFAULT_MIN_KELVIN = 2700  # 370 mireds
DEFAULT_MAX_KELVIN = 6000  # 166 mireds
DEPENDENCIES = ['knx']


class ColorTempModes(Enum):
    """Color temperature modes for config validation."""

    absolute = "DPT-7.600"
    relative = "DPT-5.001"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_BRIGHTNESS_ADDRESS): cv.string,
    vol.Optional(CONF_BRIGHTNESS_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_COLOR_ADDRESS): cv.string,
    vol.Optional(CONF_COLOR_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_COLOR_TEMP_ADDRESS): cv.string,
    vol.Optional(CONF_COLOR_TEMP_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_COLOR_TEMP_MODE, default=DEFAULT_COLOR_TEMP_MODE):
        cv.enum(ColorTempModes),
    vol.Optional(CONF_MIN_KELVIN, default=DEFAULT_MIN_KELVIN):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Optional(CONF_MAX_KELVIN, default=DEFAULT_MAX_KELVIN):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up lights for KNX platform."""
    if discovery_info is not None:
        async_add_entities_discovery(hass, discovery_info, async_add_entities)
    else:
        async_add_entities_config(hass, config, async_add_entities)


@callback
def async_add_entities_discovery(hass, discovery_info, async_add_entities):
    """Set up lights for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXLight(device))
    async_add_entities(entities)


@callback
def async_add_entities_config(hass, config, async_add_entities):
    """Set up light for KNX platform configured within platform."""
    import xknx

    group_address_tunable_white = None
    group_address_tunable_white_state = None
    group_address_color_temp = None
    group_address_color_temp_state = None
    if config[CONF_COLOR_TEMP_MODE] == ColorTempModes.absolute:
        group_address_color_temp = config.get(CONF_COLOR_TEMP_ADDRESS)
        group_address_color_temp_state = \
            config.get(CONF_COLOR_TEMP_STATE_ADDRESS)
    elif config[CONF_COLOR_TEMP_MODE] == ColorTempModes.relative:
        group_address_tunable_white = config.get(CONF_COLOR_TEMP_ADDRESS)
        group_address_tunable_white_state = \
            config.get(CONF_COLOR_TEMP_STATE_ADDRESS)

    light = xknx.devices.Light(
        hass.data[DATA_KNX].xknx,
        name=config[CONF_NAME],
        group_address_switch=config[CONF_ADDRESS],
        group_address_switch_state=config.get(CONF_STATE_ADDRESS),
        group_address_brightness=config.get(CONF_BRIGHTNESS_ADDRESS),
        group_address_brightness_state=config.get(
            CONF_BRIGHTNESS_STATE_ADDRESS),
        group_address_color=config.get(CONF_COLOR_ADDRESS),
        group_address_color_state=config.get(CONF_COLOR_STATE_ADDRESS),
        group_address_tunable_white=group_address_tunable_white,
        group_address_tunable_white_state=group_address_tunable_white_state,
        group_address_color_temperature=group_address_color_temp,
        group_address_color_temperature_state=group_address_color_temp_state,
        min_kelvin=config[CONF_MIN_KELVIN],
        max_kelvin=config[CONF_MAX_KELVIN])
    hass.data[DATA_KNX].xknx.devices.add(light)
    async_add_entities([KNXLight(light)])


class KNXLight(Light):
    """Representation of a KNX light."""

    def __init__(self, device):
        """Initialize of KNX light."""
        self.device = device

        self._min_kelvin = device.min_kelvin
        self._max_kelvin = device.max_kelvin
        self._min_mireds = \
            color_util.color_temperature_kelvin_to_mired(self._max_kelvin)
        self._max_mireds = \
            color_util.color_temperature_kelvin_to_mired(self._min_kelvin)

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""
        async def after_update_callback(device):
            """Call after device was updated."""
            await self.async_update_ha_state()
        self.device.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self):
        """No polling needed within KNX."""
        return False

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self.device.supports_color:
            if self.device.current_color is None:
                return None
            return max(self.device.current_color)
        if self.device.supports_brightness:
            return self.device.current_brightness
        return None

    @property
    def hs_color(self):
        """Return the HS color value."""
        if self.device.supports_color:
            rgb = self.device.current_color
            if rgb is None:
                return None
            return color_util.color_RGB_to_hs(*rgb)
        return None

    @property
    def color_temp(self):
        """Return the color temperature in mireds."""
        if self.device.supports_color_temperature:
            kelvin = self.device.current_color_temperature
            if kelvin is not None:
                return color_util.color_temperature_kelvin_to_mired(kelvin)
        if self.device.supports_tunable_white:
            relative_ct = self.device.current_tunable_white
            if relative_ct is not None:
                # as KNX devices typically use Kelvin we use it as base for
                # calculating ct from percent
                return color_util.color_temperature_kelvin_to_mired(
                    self._min_kelvin + (
                        (relative_ct / 255) *
                        (self._max_kelvin - self._min_kelvin)))
        return None

    @property
    def min_mireds(self):
        """Return the coldest color temp this light supports in mireds."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color temp this light supports in mireds."""
        return self._max_mireds

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return None

    @property
    def effect(self):
        """Return the current effect."""
        return None

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device.state

    @property
    def supported_features(self):
        """Flag supported features."""
        flags = 0
        if self.device.supports_brightness:
            flags |= SUPPORT_BRIGHTNESS
        if self.device.supports_color:
            flags |= SUPPORT_COLOR | SUPPORT_BRIGHTNESS
        if self.device.supports_color_temperature or \
                self.device.supports_tunable_white:
            flags |= SUPPORT_COLOR_TEMP
        return flags

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
        hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)
        mireds = kwargs.get(ATTR_COLOR_TEMP, self.color_temp)

        update_brightness = ATTR_BRIGHTNESS in kwargs
        update_color = ATTR_HS_COLOR in kwargs
        update_color_temp = ATTR_COLOR_TEMP in kwargs

        # always only go one path for turning on (avoid conflicting changes
        # and weird effects)
        if self.device.supports_brightness and \
                (update_brightness and not update_color):
            # if we don't need to update the color, try updating brightness
            # directly if supported; don't do it if color also has to be
            # changed, as RGB color implicitly sets the brightness as well
            await self.device.set_brightness(brightness)
        elif self.device.supports_color and \
                (update_brightness or update_color):
            # change RGB color (includes brightness)
            # if brightness or hs_color was not yet set use the default value
            # to calculate RGB from as a fallback
            if brightness is None:
                brightness = DEFAULT_BRIGHTNESS
            if hs_color is None:
                hs_color = DEFAULT_COLOR
            await self.device.set_color(
                color_util.color_hsv_to_RGB(*hs_color, brightness * 100 / 255))
        elif self.device.supports_color_temperature and \
                update_color_temp:
            # change color temperature without ON telegram
            kelvin = int(color_util.color_temperature_mired_to_kelvin(mireds))
            if kelvin > self._max_kelvin:
                kelvin = self._max_kelvin
            elif kelvin < self._min_kelvin:
                kelvin = self._min_kelvin
            await self.device.set_color_temperature(kelvin)
        elif self.device.supports_tunable_white and \
                update_color_temp:
            # calculate relative_ct from Kelvin to fit typical KNX devices
            kelvin = int(color_util.color_temperature_mired_to_kelvin(mireds))
            relative_ct = int(255 * (kelvin - self._min_kelvin) /
                              (self._max_kelvin - self._min_kelvin))
            await self.device.set_tunable_white(relative_ct)
        else:
            # no color/brightness change requested, so just turn it on
            await self.device.set_on()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.device.set_off()
