import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .synapse.base_entity import SynapseBaseEntity
from .synapse.bridge import SynapseBridge
from .synapse.const import DOMAIN, SynapseButtonDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.app_data.get("button")
    if entities is not None:
      async_add_entities(SynapseButton(hass, bridge, entity) for entity in entities)

class SynapseButton(SynapseBaseEntity, ButtonEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        bridge: SynapseBridge,
        entity: SynapseButtonDefinition,
    ):
        super().__init__(hass, bridge, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def device_class(self):
        return self.entity.get("device_class")

    @callback
    async def async_press(self, **kwargs) -> None:
        """Handle the button press."""
        self.hass.bus.async_fire(
            self.bridge.event_name("press"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )
