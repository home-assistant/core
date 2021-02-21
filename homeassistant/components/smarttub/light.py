"""Platform for light integration."""
import logging

from smarttub import SpaLight

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    EFFECT_COLORLOOP,
    SUPPORT_BRIGHTNESS,
    SUPPORT_EFFECT,
    LightEntity,
)

from .const import (
    DEFAULT_LIGHT_INTENSITY,
    DEFAULT_LIGHT_MODE,
    DOMAIN,
    SMARTTUB_CONTROLLER,
)
from .entity import SmartTubEntity
from .helpers import get_spa_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up entities for any lights in the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = [
        SmartTubLight(controller.coordinator, light)
        for spa in controller.spas
        for light in await spa.get_lights()
    ]

    async_add_entities(entities)


class SmartTubLight(SmartTubEntity, LightEntity):
    """A light on a spa."""

    def __init__(self, coordinator, light):
        """Initialize the entity."""
        super().__init__(coordinator, light.spa, "light")
        self.light_zone = light.zone

    @property
    def light(self) -> SpaLight:
        """Return the underlying SpaLight object for this entity."""
        return self.coordinator.data[self.spa.id]["lights"][self.light_zone]

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this light entity."""
        return super().unique_id + f"-{self.light_zone}"

    @property
    def name(self) -> str:
        """Return a name for this light entity."""
        spa_name = get_spa_name(self.spa)
        return f"{spa_name} light {self.light_zone}"

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""

        # SmartTub intensity is 0..100
        return self._smarttub_to_hass_brightness(self.light.intensity)

    @staticmethod
    def _smarttub_to_hass_brightness(intensity):
        if intensity in (0, 1):
            return 0
        return intensity * 255 / 100

    @staticmethod
    def _hass_to_smarttub_brightness(brightness):
        return brightness * 100 / 255

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self.light.mode != SpaLight.LightMode.OFF

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_EFFECT

    @property
    def effect(self):
        """Return the current effect."""
        if self.light.mode == SpaLight.LightMode.HIGH_SPEED_WHEEL:
            return EFFECT_COLORLOOP
        return None

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return [EFFECT_COLORLOOP]

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""

        mode = SpaLight.LightMode[DEFAULT_LIGHT_MODE]

        if ATTR_BRIGHTNESS in kwargs:
            intensity = self._hass_to_smarttub_brightness(kwargs[ATTR_BRIGHTNESS])
        else:
            intensity = DEFAULT_LIGHT_INTENSITY

        if kwargs.get(ATTR_EFFECT) == EFFECT_COLORLOOP:
            mode = self.light.LightMode.HIGH_SPEED_WHEEL

        await self.light.set_mode(mode, intensity)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.light.set_mode(self.light.LightMode.OFF, 0)
        await self.coordinator.async_request_refresh()
