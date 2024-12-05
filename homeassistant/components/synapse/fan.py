import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.fan import FanEntity

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseFanDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("fan")
    if entities is not None:
      async_add_entities(SynapseFan(hass, bridge, entity) for entity in entities)


class SynapseFan(SynapseBaseEntity, FanEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseFanDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def current_direction(self):
        return self.entity.get("current_direction")

    @property
    def is_on(self):
        return self.entity.get("is_on")

    @property
    def oscillating(self):
        return self.entity.get("oscillating")

    @property
    def percentage(self):
        return self.entity.get("percentage")

    @property
    def preset_mode(self):
        return self.entity.get("preset_mode")

    @property
    def preset_modes(self):
        return self.entity.get("preset_modes")

    @property
    def speed_count(self):
        return self.entity.get("speed_count")

    @callback
    async def async_set_direction(self, direction: str, **kwargs) -> None:
        """Proxy the request to set direction."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_direction"),
            {
                "unique_id": self.entity.get("unique_id"),
                "direction": direction,
                **kwargs,
            },
        )

    @callback
    async def async_set_preset_mode(self, preset_mode: str, **kwargs) -> None:
        """Proxy the request to set preset mode."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_preset_mode"),
            {
                "unique_id": self.entity.get("unique_id"),
                "preset_mode": preset_mode,
                **kwargs,
            },
        )

    @callback
    async def async_set_percentage(self, percentage: int, **kwargs) -> None:
        """Proxy the request to set percentage."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_percentage"),
            {
                "unique_id": self.entity.get("unique_id"),
                "percentage": percentage,
                **kwargs,
            },
        )

    @callback
    async def async_turn_on(self, **kwargs) -> None:
        """Proxy the request to turn the entity on."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_on"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_turn_off(self, **kwargs) -> None:
        """Proxy the request to turn the entity off."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_off"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_toggle(self, **kwargs) -> None:
        """Proxy the request to toggle the entity."""
        self.hass.bus.async_fire(
            self.bridge.event_name("toggle"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_oscillate(self, oscillating: bool, **kwargs) -> None:
        """Proxy the request to set oscillating."""
        self.hass.bus.async_fire(
            self.bridge.event_name("oscillate"),
            {
                "unique_id": self.entity.get("unique_id"),
                "oscillating": oscillating,
                **kwargs,
            },
        )
