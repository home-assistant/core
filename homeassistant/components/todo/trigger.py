"""Provides triggers for todo platform."""

import abc
import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import functools
import logging
from typing import TYPE_CHECKING, cast, override

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID, CONF_TARGET
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.target import TargetEntityChangeTracker, TargetSelection
from homeassistant.helpers.trigger import Trigger, TriggerActionRunner, TriggerConfig
from homeassistant.helpers.typing import ConfigType

from . import TodoItem, TodoListEntity
from .const import DATA_COMPONENT, DOMAIN, TodoItemStatus

ITEM_TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TARGET): cv.TARGET_FIELDS,
    }
)


_LOGGER = logging.getLogger(__name__)


def get_entity(hass: HomeAssistant, entity_id: str) -> TodoListEntity:
    """Get the todo entity for the provided entity_id."""
    component: EntityComponent[TodoListEntity] = hass.data[DATA_COMPONENT]
    if not (entity := component.get_entity(entity_id)):
        raise HomeAssistantError(f"Entity does not exist: {entity_id}")
    return entity


@dataclass(frozen=True, slots=True)
class TodoItemChangeEvent:
    """Data class for todo item change event."""

    entity_id: str
    items: list[TodoItem] | None


class ItemChangeListener(TargetEntityChangeTracker):
    """Helper class to listen to todo item changes for target entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_selection: TargetSelection,
        listener: Callable[[TodoItemChangeEvent], None],
        entities_updated: Callable[[set[str]], None],
    ) -> None:
        """Initialize the item change tracker."""

        def entity_filter(entities: set[str]) -> set[str]:
            return {
                entity_id
                for entity_id in entities
                if split_entity_id(entity_id)[0] == DOMAIN
            }

        super().__init__(hass, target_selection, entity_filter)
        self._listener = listener
        self._entities_updated = entities_updated

        self._pending_listener_task: asyncio.Task[None] | None = None
        self._unsubscribe_listeners: list[CALLBACK_TYPE] = []

    @override
    @callback
    def _handle_entities_update(self, tracked_entities: set[str]) -> None:
        """Restart the listeners when the list of entities of the tracked targets is updated."""
        if self._pending_listener_task:
            self._pending_listener_task.cancel()
        self._pending_listener_task = self._hass.async_create_task(
            self._start_listening(tracked_entities)
        )

    async def _start_listening(self, tracked_entities: set[str]) -> None:
        """Start listening for todo item changes."""
        _LOGGER.debug("Tracking items for todos: %s", tracked_entities)
        for unsub in self._unsubscribe_listeners:
            unsub()

        self._entities_updated(tracked_entities)

        def _listener_wrapper(entity_id: str, items: list[TodoItem] | None) -> None:
            self._listener(TodoItemChangeEvent(entity_id=entity_id, items=items))

        self._unsubscribe_listeners = []
        for entity_id in tracked_entities:
            try:
                entity = get_entity(self._hass, entity_id)
            except HomeAssistantError:
                _LOGGER.debug("Skipping entity %s: not found", entity_id)
                continue
            _listener_wrapper(entity_id, entity.todo_items)
            unsub = entity.async_subscribe_updates(
                functools.partial(_listener_wrapper, entity_id)
            )
            self._unsubscribe_listeners.append(unsub)

    @override
    @callback
    def _unsubscribe(self) -> None:
        """Unsubscribe from all events."""
        super()._unsubscribe()
        if self._pending_listener_task:
            self._pending_listener_task.cancel()
            self._pending_listener_task = None
        for unsub in self._unsubscribe_listeners:
            unsub()


class ItemTriggerBase(Trigger, abc.ABC):
    """todo item trigger base."""

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return cast(ConfigType, ITEM_TRIGGER_SCHEMA(config))

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)

        if TYPE_CHECKING:
            assert config.target is not None
        self._target = config.target

    async def async_attach_runner(
        self, run_action: TriggerActionRunner
    ) -> CALLBACK_TYPE:
        """Attach a trigger."""

        target_selection = TargetSelection(self._target)
        if not target_selection.has_any_target:
            raise HomeAssistantError(f"No target defined in {self._target}")
        listener = ItemChangeListener(
            self._hass,
            target_selection,
            functools.partial(self._handle_item_change, run_action=run_action),
            self._handle_entities_updated,
        )
        return listener.async_setup()

    @callback
    @abc.abstractmethod
    def _handle_item_change(
        self, event: TodoItemChangeEvent, run_action: TriggerActionRunner
    ) -> None:
        """Handle todo item change event."""

    @callback
    @abc.abstractmethod
    def _handle_entities_updated(self, tracked_entities: set[str]) -> None:
        """Handle entities being added/removed from the target."""


class ItemAddedTrigger(ItemTriggerBase):
    """todo item added trigger."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)
        self._entity_item_ids: dict[str, set[str] | None] = {}

    @override
    @callback
    def _handle_item_change(
        self, event: TodoItemChangeEvent, run_action: TriggerActionRunner
    ) -> None:
        """Listen for todo item changes."""
        entity_id = event.entity_id
        if event.items is None:
            self._entity_item_ids[entity_id] = None
            return

        old_item_ids = self._entity_item_ids.get(entity_id)
        current_item_ids = {item.uid for item in event.items if item.uid is not None}
        self._entity_item_ids[entity_id] = current_item_ids
        if old_item_ids is None:
            # Entity just became available, so no old items to compare against
            return
        added_item_ids = current_item_ids - old_item_ids
        if added_item_ids:
            _LOGGER.debug(
                "Detected added items with ids %s for entity %s",
                added_item_ids,
                entity_id,
            )
            payload = {
                ATTR_ENTITY_ID: entity_id,
                "item_ids": sorted(added_item_ids),
            }
            run_action(payload, description="todo item added trigger")

    @override
    @callback
    def _handle_entities_updated(self, tracked_entities: set[str]) -> None:
        """Clear stale state for entities that left the tracked set."""
        for entity_id in set(self._entity_item_ids) - tracked_entities:
            del self._entity_item_ids[entity_id]


class ItemRemovedTrigger(ItemTriggerBase):
    """todo item removed trigger."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)
        self._entity_item_ids: dict[str, set[str] | None] = {}

    @override
    @callback
    def _handle_item_change(
        self, event: TodoItemChangeEvent, run_action: TriggerActionRunner
    ) -> None:
        """Listen for todo item changes."""
        entity_id = event.entity_id
        if event.items is None:
            self._entity_item_ids[entity_id] = None
            return

        old_item_ids = self._entity_item_ids.get(entity_id)
        current_item_ids = {item.uid for item in event.items if item.uid is not None}
        self._entity_item_ids[entity_id] = current_item_ids
        if old_item_ids is None:
            # Entity just became available, so no old items to compare against
            return
        removed_item_ids = old_item_ids - current_item_ids
        if removed_item_ids:
            _LOGGER.debug(
                "Detected removed items with ids %s for entity %s",
                removed_item_ids,
                entity_id,
            )
            payload = {
                ATTR_ENTITY_ID: entity_id,
                "item_ids": sorted(removed_item_ids),
            }
            run_action(payload, description="todo item removed trigger")

    @override
    @callback
    def _handle_entities_updated(self, tracked_entities: set[str]) -> None:
        """Clear stale state for entities that left the tracked set."""
        for entity_id in set(self._entity_item_ids) - tracked_entities:
            del self._entity_item_ids[entity_id]


class ItemCompletedTrigger(ItemTriggerBase):
    """todo item completed trigger."""

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize trigger."""
        super().__init__(hass, config)
        self._entity_completed_item_ids: dict[str, set[str] | None] = {}

    @override
    @callback
    def _handle_item_change(
        self, event: TodoItemChangeEvent, run_action: TriggerActionRunner
    ) -> None:
        """Listen for todo item changes."""
        entity_id = event.entity_id
        if event.items is None:
            self._entity_completed_item_ids[entity_id] = None
            return

        old_item_ids = self._entity_completed_item_ids.get(entity_id)
        current_item_ids = {
            item.uid
            for item in event.items
            if item.uid is not None and item.status == TodoItemStatus.COMPLETED
        }
        self._entity_completed_item_ids[entity_id] = current_item_ids
        if old_item_ids is None:
            # Entity just became available, so no old items to compare against
            return
        new_completed_item_ids = current_item_ids - old_item_ids
        if new_completed_item_ids:
            _LOGGER.debug(
                "Detected new completed items with ids %s for entity %s",
                new_completed_item_ids,
                entity_id,
            )
            payload = {
                ATTR_ENTITY_ID: entity_id,
                "item_ids": sorted(new_completed_item_ids),
            }
            run_action(payload, description="todo item completed trigger")

    @override
    @callback
    def _handle_entities_updated(self, tracked_entities: set[str]) -> None:
        """Clear stale state for entities that left the tracked set."""
        for entity_id in set(self._entity_completed_item_ids) - tracked_entities:
            del self._entity_completed_item_ids[entity_id]


TRIGGERS: dict[str, type[Trigger]] = {
    "item_added": ItemAddedTrigger,
    "item_completed": ItemCompletedTrigger,
    "item_removed": ItemRemovedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for todo platform."""
    return TRIGGERS
