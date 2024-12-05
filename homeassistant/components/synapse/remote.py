import logging

from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseRemoteDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("remote")
    if entities is not None:
      async_add_entities(SynapseRemote(hass, bridge, entity) for entity in entities)

class SynapseRemote(SynapseBaseEntity, RemoteEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseRemoteDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def current_activity(self):
        return self.entity.get("current_activity")

    @property
    def activity_list(self):
        return self.entity.get("activity_list")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @callback
    async def async_turn_on(self, **kwargs) -> None:
        """Proxy the request to turn the entity on."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_on"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_turn_off(self, **kwargs) -> None:
        """Proxy the request to turn the entity off."""
        self.hass.bus.async_fire(
            self.bridge.event_name("turn_off"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_toggle(self, **kwargs) -> None:
        """Proxy the request to toggle the entity."""
        self.hass.bus.async_fire(
            self.bridge.event_name("toggle"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_send_command(self, command: str, **kwargs) -> None:
        """Proxy the request to send a command."""
        self.hass.bus.async_fire(
            self.bridge.event_name("send_command"),
            {"unique_id": self.entity.get("unique_id"), "command": command, **kwargs},
        )

    @callback
    async def async_learn_command(self, **kwargs) -> None:
        """Proxy the request to learn a command."""
        self.hass.bus.async_fire(
            self.bridge.event_name("learn_command"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_delete_command(self, command: str, **kwargs) -> None:
        """Proxy the request to delete a command."""
        self.hass.bus.async_fire(
            self.bridge.event_name("delete_command"),
            {"unique_id": self.entity.get("unique_id"), "command": command, **kwargs},
        )

    @callback
    async def async_send_command(self, command: str, **kwargs) -> None:
        """Proxy the request to send a command."""
        self.hass.bus.async_fire(
            self.bridge.event_name("send_command"),
            {"unique_id": self.entity.get("unique_id"), "command": command, **kwargs},
        )

    @callback
    async def async_learn_command(self, **kwargs) -> None:
        """Proxy the request to learn a command."""
        self.hass.bus.async_fire(
            self.bridge.event_name("learn_command"),
            {"unique_id": self.entity.get("unique_id"), **kwargs},
        )

    @callback
    async def async_delete_command(self, command: str, **kwargs) -> None:
        """Proxy the request to delete a command."""
        self.hass.bus.async_fire(
            self.bridge.event_name("delete_command"),
            {"unique_id": self.entity.get("unique_id"), "command": command, **kwargs},
        )
