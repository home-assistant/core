"""Support for Plum Lightpad lights."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    Light,
)
import homeassistant.util.color as color_util

from . import PLUM_DATA


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Initialize the Plum Lightpad Light and GlowRing."""
    if discovery_info is None:
        return

    plum = hass.data[PLUM_DATA]

    entities = []

    if "lpid" in discovery_info:
        lightpad = plum.get_lightpad(discovery_info["lpid"])
        entities.append(GlowRing(lightpad=lightpad))

    if "llid" in discovery_info:
        logical_load = plum.get_load(discovery_info["llid"])
        entities.append(PlumLight(load=logical_load))

    if entities:
        async_add_entities(entities)


class PlumLight(Light):
    """Representation of a Plum Lightpad dimmer."""

    def __init__(self, load):
        """Initialize the light."""
        self._load = load
        self._brightness = load.level

    async def async_added_to_hass(self):
        """Subscribe to dimmerchange events."""
        self._load.add_event_listener("dimmerchange", self.dimmerchange)

    def dimmerchange(self, event):
        """Change event handler updating the brightness."""
        self._brightness = event["level"]
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._load.name

    @property
    def brightness(self) -> int:
        """Return the brightness of this switch between 0..255."""
        return self._brightness

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._brightness > 0

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._load.dimmable:
            return SUPPORT_BRIGHTNESS
        return 0

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._load.turn_on(kwargs[ATTR_BRIGHTNESS])
        else:
            await self._load.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._load.turn_off()


class GlowRing(Light):
    """Representation of a Plum Lightpad dimmer glow ring."""

    def __init__(self, lightpad):
        """Initialize the light."""
        self._lightpad = lightpad
        self._name = f"{lightpad.friendly_name} Glow Ring"

        self._state = lightpad.glow_enabled
        self._brightness = lightpad.glow_intensity * 255.0

        self._red = lightpad.glow_color["red"]
        self._green = lightpad.glow_color["green"]
        self._blue = lightpad.glow_color["blue"]

    async def async_added_to_hass(self):
        """Subscribe to configchange events."""
        self._lightpad.add_event_listener("configchange", self.configchange_event)

    def configchange_event(self, event):
        """Handle Configuration change event."""
        config = event["changes"]

        self._state = config["glowEnabled"]
        self._brightness = config["glowIntensity"] * 255.0

        self._red = config["glowColor"]["red"]
        self._green = config["glowColor"]["green"]
        self._blue = config["glowColor"]["blue"]

        self.schedule_update_ha_state()

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        return color_util.color_RGB_to_hs(self._red, self._green, self._blue)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self._name

    @property
    def brightness(self) -> int:
        """Return the brightness of this switch between 0..255."""
        return self._brightness

    @property
    def glow_intensity(self):
        """Brightness in float form."""
        return self._brightness / 255.0

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def icon(self):
        """Return the crop-portrait icon representing the glow ring."""
        return "mdi:crop-portrait"

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._lightpad.set_config({"glowIntensity": kwargs[ATTR_BRIGHTNESS]})
        elif ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            red, green, blue = color_util.color_hs_to_RGB(*hs_color)
            await self._lightpad.set_glow_color(red, green, blue, 0)
        else:
            await self._lightpad.set_config({"glowEnabled": True})

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._lightpad.set_config({"glowIntensity": kwargs[ATTR_BRIGHTNESS]})
        else:
            await self._lightpad.set_config({"glowEnabled": False})
