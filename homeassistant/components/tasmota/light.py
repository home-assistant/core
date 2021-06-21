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
    ATTR_WHITE,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_HS,
    COLOR_MODE_ONOFF,
    COLOR_MODE_WHITE,
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


def clamp(value):
    """Clamp value to the range 0..255."""
    return min(max(value, 0), 255)


def scale_brightness(brightness):
    """Scale brightness from 0..255 to 1..100."""
    brightness_normalized = brightness / DEFAULT_BRIGHTNESS_MAX
    device_brightness = min(
        round(brightness_normalized * TASMOTA_BRIGHTNESS_MAX),
        TASMOTA_BRIGHTNESS_MAX,
    )
    # Make sure the brightness is not rounded down to 0
    return max(device_brightness, 1)


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
        self._hs = None

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

        if light_type in [LIGHT_TYPE_RGB, LIGHT_TYPE_RGBW, LIGHT_TYPE_RGBCW]:
            # Mark HS support for RGBW light because we don't have direct control over the
            # white channel, so the base component's RGB->RGBW translation does not work
            self._supported_color_modes.add(COLOR_MODE_HS)
            self._color_mode = COLOR_MODE_HS

        if light_type == LIGHT_TYPE_RGBW:
            self._supported_color_modes.add(COLOR_MODE_WHITE)

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
            if "color_hs" in attributes:
                self._hs = attributes["color_hs"]
            if "color_temp" in attributes:
                self._color_temp = attributes["color_temp"]
            if "effect" in attributes:
                self._effect = attributes["effect"]
            if "white_value" in attributes:
                white_value = float(attributes["white_value"])
                percent_white = white_value / TASMOTA_BRIGHTNESS_MAX
                self._white_value = percent_white * 255
            if self._tasmota_entity.light_type == LIGHT_TYPE_RGBW:
                # Tasmota does not support RGBW mode, set mode to white or hs
                if self._white_value == 0:
                    self._color_mode = COLOR_MODE_HS
                else:
                    self._color_mode = COLOR_MODE_WHITE
            elif self._tasmota_entity.light_type == LIGHT_TYPE_RGBCW:
                # Tasmota does not support RGBWW mode, set mode to ct or hs
                if self._white_value == 0:
                    self._color_mode = COLOR_MODE_HS
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
    def hs_color(self):
        """Return the hs color value."""
        if self._hs is None:
            return None
        hs_color = self._hs
        return [hs_color[0], hs_color[1]]

    @property
    def force_update(self):
        """Force update."""
        return False

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

        if ATTR_HS_COLOR in kwargs and COLOR_MODE_HS in supported_color_modes:
            hs_color = kwargs[ATTR_HS_COLOR]
            attributes["color_hs"] = [hs_color[0], hs_color[1]]

        if ATTR_WHITE in kwargs and COLOR_MODE_WHITE in supported_color_modes:
            attributes["white_value"] = scale_brightness(kwargs[ATTR_WHITE])

        if ATTR_TRANSITION in kwargs:
            attributes["transition"] = kwargs[ATTR_TRANSITION]

        if ATTR_BRIGHTNESS in kwargs and brightness_supported(supported_color_modes):
            attributes["brightness"] = scale_brightness(kwargs[ATTR_BRIGHTNESS])

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
