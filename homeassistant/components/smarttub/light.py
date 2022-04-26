"""Platform for light integration."""
from smarttub import SpaLight

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    EFFECT_COLORLOOP,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_LIGHTS,
    DEFAULT_LIGHT_BRIGHTNESS,
    DEFAULT_LIGHT_EFFECT,
    DOMAIN,
    SMARTTUB_CONTROLLER,
)
from .entity import SmartTubEntity
from .helpers import get_spa_name


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entities for any lights in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = [
        SmartTubLight(controller.coordinator, light)
        for spa in controller.spas
        for light in controller.coordinator.data[spa.id][ATTR_LIGHTS].values()
    ]

    async_add_entities(entities)


class SmartTubLight(SmartTubEntity, LightEntity):
    """A light on a spa."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.EFFECT

    def __init__(self, coordinator, light):
        """Initialize the entity."""
        super().__init__(coordinator, light.spa, "light")
        self.light_zone = light.zone

    @property
    def light(self) -> SpaLight:
        """Return the underlying SpaLight object for this entity."""
        return self.coordinator.data[self.spa.id][ATTR_LIGHTS][self.light_zone]

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this light entity."""
        return f"{super().unique_id}-{self.light_zone}"

    @property
    def name(self) -> str:
        """Return a name for this light entity."""
        spa_name = get_spa_name(self.spa)
        return f"{spa_name} Light {self.light_zone}"

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""

        # SmartTub intensity is 0..100
        return self._smarttub_to_hass_brightness(self.light.intensity)

    @staticmethod
    def _smarttub_to_hass_brightness(intensity):
        if intensity in (0, 1):
            return 0
        return round(intensity * 255 / 100)

    @staticmethod
    def _hass_to_smarttub_brightness(brightness):
        return round(brightness * 100 / 255)

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self.light.mode != SpaLight.LightMode.OFF

    @property
    def effect(self):
        """Return the current effect."""
        mode = self.light.mode.name.lower()
        if mode in self.effect_list:
            return mode
        return None

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        effects = [
            effect
            for effect in map(self._light_mode_to_effect, SpaLight.LightMode)
            if effect is not None
        ]

        return effects

    @staticmethod
    def _light_mode_to_effect(light_mode: SpaLight.LightMode):
        if light_mode == SpaLight.LightMode.OFF:
            return None
        if light_mode == SpaLight.LightMode.HIGH_SPEED_COLOR_WHEEL:
            return EFFECT_COLORLOOP

        return light_mode.name.lower()

    @staticmethod
    def _effect_to_light_mode(effect):
        if effect == EFFECT_COLORLOOP:
            return SpaLight.LightMode.HIGH_SPEED_COLOR_WHEEL

        return SpaLight.LightMode[effect.upper()]

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""

        mode = self._effect_to_light_mode(kwargs.get(ATTR_EFFECT, DEFAULT_LIGHT_EFFECT))
        intensity = self._hass_to_smarttub_brightness(
            kwargs.get(ATTR_BRIGHTNESS, DEFAULT_LIGHT_BRIGHTNESS)
        )

        await self.light.set_mode(mode, intensity)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.light.set_mode(SpaLight.LightMode.OFF, 0)
        await self.coordinator.async_request_refresh()
