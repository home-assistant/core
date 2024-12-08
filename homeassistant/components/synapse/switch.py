import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .synapse.base_entity import SynapseBaseEntity
from .synapse.bridge import SynapseBridge
from .synapse.const import DOMAIN, SynapseSwitchDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.app_data.get("switch")
    if entities is not None:
      async_add_entities(SynapseSwitch(hass, bridge, entity) for entity in entities)

class SynapseSwitch(SynapseBaseEntity, SwitchEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        bridge: SynapseBridge,
        entity: SynapseSwitchDefinition,
    ):
        super().__init__(hass, bridge, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def is_on(self):
        return self.entity.get("is_on")

    @property
    def device_class(self):
        return self.entity.get("device_class")

    @callback
    async def async_turn_on(self, **kwargs) -> None:
        """Handle the switch press."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_on"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )

    @callback
    async def async_turn_off(self, **kwargs) -> None:
        """Handle the switch press."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_off"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )

    @callback
    async def async_turn_toggle(self, **kwargs) -> None:
        """Handle the switch press."""
        self.hass.bus.async_fire(
            self.bridge.event_name("toggle"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )
