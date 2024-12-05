import logging

from homeassistant.components.lawnmower import LawnMowerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseLawnMowerDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("lawnmower")
    if entities is not None:
      async_add_entities(SynapseLawnMower(hass, bridge, entity) for entity in entities)

class SynapseLawnMower(SynapseBaseEntity, LawnMowerEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseLawnMowerDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def activity(self):
        return self.entity.get("activity")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @callback
    async def async_start_mowing(self, **kwargs) -> None:
        """Proxy the request to start mowing."""
        self.hass.bus.async_fire(
            self.bridge.event_name("start_mowing"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )

    @callback
    async def async_dock(self, **kwargs) -> None:
        """Proxy the request to dock."""
        self.hass.bus.async_fire(
            self.bridge.event_name("dock"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )

    @callback
    async def async_pause(self, **kwargs) -> None:
        """Proxy the request to pause."""
        self.hass.bus.async_fire(
            self.bridge.event_name("pause"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )
