"""Support for Tasmota lights."""
from hatasmota.light import (
    LIGHT_TYPE_COLDWARM,
    LIGHT_TYPE_NONE,
    LIGHT_TYPE_RGB,
    LIGHT_TYPE_RGBCW,
    LIGHT_TYPE_RGBW,
)

from homeassistant.components import light
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.color as color_util

from .const import DATA_REMOVE_DISCOVER_COMPONENT, DOMAIN as TASMOTA_DOMAIN
from .discovery import TASMOTA_DISCOVERY_ENTITY_NEW
from .mixins import TasmotaAvailability, TasmotaDiscoveryUpdate

DEFAULT_BRIGHTNESS_MAX = 255
TASMOTA_BRIGHTNESS_MAX = 100


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Tasmota light dynamically through discovery."""

    @callback
    def async_discover(tasmota_entity, discovery_hash):
        """Discover and add a Tasmota light."""
        async_add_entities(
            [TasmotaLight(tasmota_entity=tasmota_entity, discovery_hash=discovery_hash)]
        )

    hass.data[
        DATA_REMOVE_DISCOVER_COMPONENT.format(light.DOMAIN)
    ] = async_dispatcher_connect(
        hass,
        TASMOTA_DISCOVERY_ENTITY_NEW.format(light.DOMAIN, TASMOTA_DOMAIN),
        async_discover,
    )


class TasmotaLight(
    TasmotaAvailability,
    TasmotaDiscoveryUpdate,
    LightEntity,
):
    """Representation of a Tasmota light."""

    def __init__(self, **kwds):
        """Initialize Tasmota light."""
        self._state = False
        self._supported_features = 0

        self._brightness = None
        self._color_temp = None
        self._effect = None
        self._hs = None
        self._white_value = None
        self._flash_times = None

        super().__init__(
            discovery_update=self.discovery_update,
            **kwds,
        )

        self._setup_from_entity()

    async def discovery_update(self, update, write_state=True):
        """Handle updated discovery message."""
        await super().discovery_update(update, write_state=False)
        self._setup_from_entity()
        self.async_write_ha_state()

    def _setup_from_entity(self):
        """(Re)Setup the entity."""
        supported_features = 0
        light_type = self._tasmota_entity.light_type

        if light_type != LIGHT_TYPE_NONE:
            supported_features |= SUPPORT_BRIGHTNESS
            supported_features |= SUPPORT_TRANSITION

        if light_type in [LIGHT_TYPE_COLDWARM, LIGHT_TYPE_RGBCW]:
            supported_features |= SUPPORT_COLOR_TEMP

        if light_type in [LIGHT_TYPE_RGB, LIGHT_TYPE_RGBW, LIGHT_TYPE_RGBCW]:
            supported_features |= SUPPORT_COLOR
            supported_features |= SUPPORT_EFFECT

        if light_type in [LIGHT_TYPE_RGBW, LIGHT_TYPE_RGBCW]:
            supported_features |= SUPPORT_WHITE_VALUE

        self._supported_features = supported_features

    @callback
    def state_updated(self, state, **kwargs):
        """Handle state updates."""
        self._state = state
        attributes = kwargs.get("attributes")
        if attributes:
            if "brightness" in attributes:
                brightness = float(attributes["brightness"])
                percent_bright = brightness / TASMOTA_BRIGHTNESS_MAX
                self._brightness = percent_bright * 255
            if "color" in attributes:
                color = attributes["color"]
                self._hs = color_util.color_RGB_to_hs(*color)
            if "color_temp" in attributes:
                self._color_temp = attributes["color_temp"]
            if "effect" in attributes:
                self._effect = attributes["effect"]
            if "white_value" in attributes:
                white_value = float(attributes["white_value"])
                percent_white = white_value / TASMOTA_BRIGHTNESS_MAX
                self._white_value = percent_white * 255
            if self._white_value == 0:
                self._color_temp = None
                self._white_value = None
            if self._white_value is not None and self._white_value > 0:
                self._hs = None
        self.async_write_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the color temperature in mired."""
        return self._color_temp

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._tasmota_entity.min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._tasmota_entity.max_mireds

    @property
    def effect(self):
        """Return the current effect."""
        return self._effect

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return self._tasmota_entity.effect_list

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._hs

    @property
    def white_value(self):
        """Return the white property."""
        return self._white_value

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        supported_features = self._supported_features

        attributes = {}

        if ATTR_HS_COLOR in kwargs and supported_features & SUPPORT_COLOR:
            hs_color = kwargs[ATTR_HS_COLOR]
            attributes["color"] = {}

            rgb = color_util.color_hsv_to_RGB(hs_color[0], hs_color[1], 100)
            attributes["color"] = [rgb[0], rgb[1], rgb[2]]

        if ATTR_TRANSITION in kwargs:
            attributes["transition"] = kwargs[ATTR_TRANSITION]

        if ATTR_BRIGHTNESS in kwargs and supported_features & SUPPORT_BRIGHTNESS:
            brightness_normalized = kwargs[ATTR_BRIGHTNESS] / DEFAULT_BRIGHTNESS_MAX
            device_brightness = min(
                round(brightness_normalized * TASMOTA_BRIGHTNESS_MAX),
                TASMOTA_BRIGHTNESS_MAX,
            )
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(device_brightness, 1)
            attributes["brightness"] = device_brightness

        if ATTR_COLOR_TEMP in kwargs and supported_features & SUPPORT_COLOR_TEMP:
            attributes["color_temp"] = int(kwargs[ATTR_COLOR_TEMP])

        if ATTR_EFFECT in kwargs:
            attributes["effect"] = kwargs[ATTR_EFFECT]

        if ATTR_WHITE_VALUE in kwargs:
            white_value_normalized = kwargs[ATTR_WHITE_VALUE] / DEFAULT_BRIGHTNESS_MAX
            device_white_value = min(
                round(white_value_normalized * TASMOTA_BRIGHTNESS_MAX),
                TASMOTA_BRIGHTNESS_MAX,
            )
            attributes["white_value"] = device_white_value

        self._tasmota_entity.set_state(True, attributes)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        attributes = {"state": "OFF"}

        if ATTR_TRANSITION in kwargs:
            attributes["transition"] = kwargs[ATTR_TRANSITION]

        self._tasmota_entity.set_state(False, attributes)
