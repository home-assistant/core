import logging

from datetime import date
from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseDateDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("date")
    if entities is not None:
        async_add_entities(SynapseDate(hass, bridge, entity) for entity in entities)

class SynapseDate(SynapseBaseEntity, DateEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseDateDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def native_value(self):
        return date.fromisoformat(self.entity.get("native_value"))

    @callback
    async def async_set_value(self, value: date, **kwargs) -> None:
        """Proxy the request to set the value."""
        self.hass.bus.async_fire(
            self.bridge.event_name("set_value"),
            {"unique_id": self.entity.get("unique_id"), "value": value, **kwargs},
        )
