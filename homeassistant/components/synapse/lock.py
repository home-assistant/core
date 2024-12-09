import logging

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .synapse.base_entity import SynapseBaseEntity
from .synapse.bridge import SynapseBridge
from .synapse.const import DOMAIN, SynapseLockDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.app_data.get("lock")
    if entities is not None:
      async_add_entities(SynapseLock(hass, bridge, entity) for entity in entities)

class SynapseLock(SynapseBaseEntity, LockEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        bridge: SynapseBridge,
        entity: SynapseLockDefinition,
    ):
        super().__init__(hass, bridge, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def changed_by(self):
        return self.entity.get("changed_by")

    @property
    def code_format(self):
        return self.entity.get("code_format")

    @property
    def is_locked(self):
        return self.entity.get("is_locked")

    @property
    def is_locking(self):
        return self.entity.get("is_locking")

    @property
    def is_unlocking(self):
        return self.entity.get("is_unlocking")

    @property
    def is_jammed(self):
        return self.entity.get("is_jammed")

    @property
    def is_opening(self):
        return self.entity.get("is_opening")

    @property
    def is_open(self):
        return self.entity.get("is_open")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @callback
    async def async_lock(self, **kwargs) -> None:
        """Proxy the request to lock."""
        self.hass.bus.async_fire(
            self.bridge.event_name("lock"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )

    @callback
    async def async_unlock(self, **kwargs) -> None:
        """Proxy the request to unlock."""
        self.hass.bus.async_fire(
            self.bridge.event_name("unlock"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )

    @callback
    async def async_open(self, **kwargs) -> None:
        """Proxy the request to open."""
        self.hass.bus.async_fire(
            self.bridge.event_name("open"), {"unique_id": self.entity.get("unique_id"), **kwargs}
        )
