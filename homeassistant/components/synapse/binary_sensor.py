import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import SynapseBridge
from .const import DOMAIN, SynapseBinarySensorDefinition
from .base_entity import SynapseBaseEntity

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("binary_sensor")
    if entities is not None:
      async_add_entities(SynapseBinarySensor(hass, bridge, entity) for entity in entities)

class SynapseBinarySensor(SynapseBaseEntity, BinarySensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseBinarySensorDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def device_class(self):
        return self.entity.get("device_class")

    @property
    def is_on(self):
        return self.entity.get("is_on")
