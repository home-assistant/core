import logging

from homeassistant.components.light import LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseLightDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("light")
    if entities is not None:
      async_add_entities(SynapseLight(hass, bridge, entity) for entity in entities)

class SynapseLight(SynapseBaseEntity, LightEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseLightDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def brightness(self):
        return self.entity.get("brightness")

    @property
    def color_mode(self):
        return self.entity.get("color_mode")

    @property
    def color_temp_kelvin(self):
        return self.entity.get("color_temp_kelvin")

    @property
    def effect(self):
        return self.entity.get("effect")

    @property
    def effect_list(self):
        return self.entity.get("effect_list")

    @property
    def hs_color(self):
        return self.entity.get("hs_color")

    @property
    def is_on(self):
        return self.entity.get("is_on")

    @property
    def max_color_temp_kelvin(self):
        return self.entity.get("max_color_temp_kelvin")

    @property
    def min_color_temp_kelvin(self):
        return self.entity.get("min_color_temp_kelvin")

    @property
    def rgb_color(self):
        return self.entity.get("rgb_color")

    @property
    def rgbw_color(self):
        return self.entity.get("rgbw_color")

    @property
    def rgbww_color(self):
        return self.entity.get("rgbww_color")

    @property
    def supported_color_modes(self):
        return self.entity.get("supported_color_modes")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @property
    def xy_color(self):
        return self.entity.get("xy_color")

    @callback
    async def async_turn_on(self, **kwargs) -> None:
        """Proxy the request to turn the entity on."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_on"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )

    @callback
    async def async_turn_off(self, **kwargs) -> None:
        """Proxy the request to turn the entity off."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_off"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )
