import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .synapse.base_entity import SynapseBaseEntity
from .synapse.bridge import SynapseBridge
from .synapse.const import DOMAIN, SynapseSelectDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.app_data.get("select")
    if entities is not None:
      async_add_entities(SynapseSelect(hass, bridge, entity) for entity in entities)

class SynapseSelect(SynapseBaseEntity, SelectEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        bridge: SynapseBridge,
        entity: SynapseSelectDefinition,
    ):
        super().__init__(hass, bridge, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def current_option(self):
        return self.entity.get("current_option")

    @property
    def options(self):
        return self.entity.get("options")

    @callback
    async def async_select_option(self, option: str, **kwargs) -> None:
        """Proxy the request to select an option."""
        self.hass.bus.async_fire(
            self.bridge.event_name("select_option"),
            {"unique_id": self.entity.get("unique_id"), "option": option, **kwargs},
        )
