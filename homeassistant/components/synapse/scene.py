import logging

from homeassistant.components.scene import Scene as SceneEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseSceneDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("scene")
    if entities is not None:
      async_add_entities(SynapseScene(hass, bridge, entity) for entity in entities)

class SynapseScene(SynapseBaseEntity, SceneEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseSceneDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @callback
    async def async_activate(self) -> None:
        """Handle the scene press."""
        self.hass.bus.async_fire(
            self.bridge.event_name("activate"), {"unique_id": self.entity.get("unique_id")}
        )
