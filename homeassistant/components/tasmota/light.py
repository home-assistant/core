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
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
    brightness_supported,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_REMOVE_DISCOVER_COMPONENT
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
        TASMOTA_DISCOVERY_ENTITY_NEW.format(light.DOMAIN),
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
        self._supported_color_modes = None
        self._supported_features = 0

        self._brightness = None
        self._color_mode = None
        self._color_temp = None
        self._effect = None
        self._white_value = None
        self._flash_times = None
        self._rgb = None
        self._rgbw = None

        super().__init__(
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
        self._supported_color_modes = set()
        supported_features = 0
        light_type = self._tasmota_entity.light_type

        if light_type in [LIGHT_TYPE_RGB, LIGHT_TYPE_RGBCW]:
            self._supported_color_modes.add(COLOR_MODE_RGB)
            self._color_mode = COLOR_MODE_RGB

        if light_type == LIGHT_TYPE_RGBW:
            self._supported_color_modes.add(COLOR_MODE_RGBW)
            self._color_mode = COLOR_MODE_RGBW

        if light_type in [LIGHT_TYPE_COLDWARM, LIGHT_TYPE_RGBCW]:
            self._supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
            self._color_mode = COLOR_MODE_COLOR_TEMP

        if light_type != LIGHT_TYPE_NONE and not self._supported_color_modes:
            self._supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
            self._color_mode = COLOR_MODE_BRIGHTNESS

        if not self._supported_color_modes:
            self._supported_color_modes.add(COLOR_MODE_ONOFF)
            self._color_mode = COLOR_MODE_ONOFF

        if light_type in [LIGHT_TYPE_RGB, LIGHT_TYPE_RGBW, LIGHT_TYPE_RGBCW]:
            supported_features |= SUPPORT_EFFECT

        if self._tasmota_entity.supports_transition:
            supported_features |= SUPPORT_TRANSITION

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

                def clamp(value):
                    """Clamp value to the range 0..255."""
                    return min(max(value, 0), 255)

                rgb = attributes["color"]
                # Tasmota's RGB color is adjusted for brightness, compensate
                red_compensated = clamp(round(rgb[0] / self._brightness * 255))
                green_compensated = clamp(round(rgb[1] / self._brightness * 255))
                blue_compensated = clamp(round(rgb[2] / self._brightness * 255))
                self._rgb = [red_compensated, green_compensated, blue_compensated]
            if "color_temp" in attributes:
                self._color_temp = attributes["color_temp"]
            if "effect" in attributes:
                self._effect = attributes["effect"]
            if "white_value" in attributes:
                white_value = float(attributes["white_value"])
                percent_white = white_value / TASMOTA_BRIGHTNESS_MAX
                self._white_value = percent_white * 255
            if self._tasmota_entity.light_type == LIGHT_TYPE_RGBCW:
                # Tasmota does not support RGBWW mode, set mode to ct or rgb
                if self._white_value == 0:
                    self._color_mode = COLOR_MODE_RGB
                else:
                    self._color_mode = COLOR_MODE_COLOR_TEMP

        self.async_write_ha_state()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        return self._color_mode

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
    def rgb_color(self):
        """Return the rgb color value."""
        return self._rgb

    @property
    def rgbw_color(self):
        """Return the rgbw color value."""
        if self._rgb is None or self._white_value is None:
            return None
        return [*self._rgb, self._white_value]

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def supported_color_modes(self):
        """Flag supported color modes."""
        return self._supported_color_modes

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        supported_color_modes = self._supported_color_modes

        attributes = {}

        if ATTR_RGB_COLOR in kwargs and COLOR_MODE_RGB in supported_color_modes:
            rgb = kwargs[ATTR_RGB_COLOR]
            attributes["color"] = [rgb[0], rgb[1], rgb[2]]

        if ATTR_RGBW_COLOR in kwargs and COLOR_MODE_RGBW in supported_color_modes:
            rgbw = kwargs[ATTR_RGBW_COLOR]
            # Tasmota does not support direct RGBW control, the light must be set to
            # either white mode or color mode. Set the mode according to max of rgb
            # and white channels
            if max(rgbw[0:3]) > rgbw[3]:
                attributes["color"] = [rgbw[0], rgbw[1], rgbw[2]]
            else:
                white_value_normalized = rgbw[3] / DEFAULT_BRIGHTNESS_MAX
                device_white_value = min(
                    round(white_value_normalized * TASMOTA_BRIGHTNESS_MAX),
                    TASMOTA_BRIGHTNESS_MAX,
                )
                attributes["white_value"] = device_white_value

        if ATTR_TRANSITION in kwargs:
            attributes["transition"] = kwargs[ATTR_TRANSITION]

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(supported_color_modes):
            brightness_normalized = kwargs[ATTR_BRIGHTNESS] / DEFAULT_BRIGHTNESS_MAX
            device_brightness = min(
                round(brightness_normalized * TASMOTA_BRIGHTNESS_MAX),
                TASMOTA_BRIGHTNESS_MAX,
            )
            # Make sure the brightness is not rounded down to 0
            device_brightness = max(device_brightness, 1)
            attributes["brightness"] = device_brightness

        if ATTR_COLOR_TEMP in kwargs and COLOR_MODE_COLOR_TEMP in supported_color_modes:
            attributes["color_temp"] = int(kwargs[ATTR_COLOR_TEMP])

        if ATTR_EFFECT in kwargs:
            attributes["effect"] = kwargs[ATTR_EFFECT]

        self._tasmota_entity.set_state(True, attributes)

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        attributes = {"state": "OFF"}

        if ATTR_TRANSITION in kwargs:
            attributes["transition"] = kwargs[ATTR_TRANSITION]

        self._tasmota_entity.set_state(False, attributes)
