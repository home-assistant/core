import logging

from homeassistant.components.update import UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseUpdateDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("update")
    if entities is not None:
      async_add_entities(SynapseUpdate(hass, bridge, entity) for entity in entities)

class SynapseUpdate(SynapseBaseEntity, UpdateEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseUpdateDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def auto_update(self):
        return self.entity.get("auto_update")

    @property
    def device_class(self):
        return self.entity.get("device_class")

    @property
    def in_progress(self):
        return self.entity.get("in_progress")

    @property
    def installed_version(self):
        return self.entity.get("installed_version")

    @property
    def latest_version(self):
        return self.entity.get("latest_version")

    @property
    def release_notes(self):
        return self.entity.get("release_notes")

    @property
    def release_summary(self):
        return self.entity.get("release_summary")

    @property
    def release_url(self):
        return self.entity.get("release_url")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @property
    def title(self):
        return self.entity.get("title")

    @callback
    async def async_install(self, **kwargs) -> None:
        """Proxy the request to install."""
        self.hass.bus.async_fire(
            self.bridge.event_name("install"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )
