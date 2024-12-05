import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.todolist import TodoListEntity

from .base_entity import SynapseBaseEntity
from .bridge import SynapseBridge
from .const import DOMAIN, SynapseTodoListDefinition

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup the router platform."""
    bridge: SynapseBridge = hass.data[DOMAIN][config_entry.entry_id]
    entities = bridge.config_data.get("todolist")
    if entities is not None:
      async_add_entities(SynapseTodoList(hass, bridge, entity) for entity in entities)

class SynapseTodoList(SynapseBaseEntity, TodoListEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        hub: SynapseBridge,
        entity: SynapseTodoListDefinition,
    ):
        super().__init__(hass, hub, entity)
        self.logger = logging.getLogger(__name__)

    @property
    def todo_items(self):
        return self.entity.get("todo_items")

    @property
    def supported_features(self):
        return self.entity.get("supported_features")

    @callback
    async def async_create_todo_item(self, item: str, **kwargs) -> None:
        """Proxy the request to create a todo item."""
        self.hass.bus.async_fire(
            self.bridge.event_name("create_todo_item"),
            {"unique_id": self.entity.get("unique_id"), "item": item, **kwargs},
        )

    @callback
    async def async_delete_todo_item(self, item_id: str, **kwargs) -> None:
        """Proxy the request to delete a todo item."""
        self.hass.bus.async_fire(
            self.bridge.event_name("delete_todo_item"),
            {"unique_id": self.entity.get("unique_id"), "item_id": item_id, **kwargs},
        )

    @callback
    async def async_move_todo_item(self, item_id: str, position: int, **kwargs) -> None:
        """Proxy the request to move a todo item."""
        self.hass.bus.async_fire(
            self.bridge.event_name("move_todo_item"),
            {
                "unique_id": self.entity.get("unique_id"),
                "item_id": item_id,
                "position": position,
                **kwargs,
            },
        )
