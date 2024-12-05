import logging

from homeassistant.components.siren import SirenEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseSirenDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("siren")
    if entities is not None:
      async_add_entities(SynapseSiren(hass, bridge, entity) for entity in entities)


class SynapseSiren(SynapseBaseEntity, SirenEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseSirenDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def is_on(self):
        return self.entity.get("is_on")

    @property
    def available_tones(self):
        return self.entity.get("available_tones")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

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
