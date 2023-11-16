"""Helpers to execute rasc entities."""
from __future__ import annotations

from collections.abc import Iterator, MutableMapping, MutableSequence
from typing import Any, TypeVar

from homeassistant.components.device_automation import action as device_action
from homeassistant.core import Context, HomeAssistant

from . import config_validation as cv

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


DOMAIN = "rascalscheduler"
CONFIG_ACTION_ID = "action_id"
CONFIG_ENTITY_ID = "entity_id"
CONFIG_ACTION_ENTITY = "action_entity"


SCHEDULED_STATE = "scheduled"
READY_STATE = "ready"
ACTIVE_STATE = "active"
COMPLETED_STATE = "completed"


RASC_START = "start"
RASC_COMPLETE = "complete"
RASC_RESPONSE = "rasc_response"


class RoutineEntity:
    """A class that describes routine entities for Rascal Scheduler."""

    def __init__(
        self,
        routine_id: str,
        actions: dict[str, ActionEntity],
    ) -> None:
        """Initialize a routine entity."""
        self.routine_id = routine_id
        self.actions = actions


class ActionEntity:
    """Initialize a routine entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        action: dict[str, Any],
        action_id: str,
        action_state: str | None,
        routine_id: str,
        variables: dict[str, Any],
        context: Context | None,
    ) -> None:
        """Initialize a routine entity."""
        self._hass = hass
        self.action = action
        self.action_id = action_id

        if action_state is None:
            self.action_state = SCHEDULED_STATE
        else:
            self.action_state = action_state

        self.parent: list[str] = []
        self.children: list[str] = []
        self.routine_id = routine_id
        self.variables = variables
        self.context = context

    async def attach_triggered(self) -> None:
        """Trigger the function."""
        # print("[rascal] attach_triggered")
        action = cv.determine_script_action(self.action)

        try:
            handler = f"_async_{action}_step"
            await getattr(self, handler)()

            # self.hass.bus.async_fire(EVENT_ACTION_COMPLETED, {CONFIG_ACTION_ENTITY: self})
        except Exception:  # pylint: disable=broad-except
            return
            # print(ex)

    async def _async_device_step(self) -> None:
        """Execute device automation."""
        # print("device automation")
        await device_action.async_call_action_from_config(
            self._hass, self.action, self.variables, self.context
        )


class Queue(MutableMapping[_KT, _VT]):
    """Representation of an queue for rascal scheduler."""

    __slots__ = ("_queue",)

    _queue: dict[_KT, _VT]

    def __init__(self, queue: Any) -> None:
        """Initialize a queue entity."""
        if queue is None:
            self._queue = {}
        else:
            self._queue = queue

    def __getitem__(self, __key: _KT) -> _VT:
        """Get item."""
        return self._queue[__key]

    def __delitem__(self, __key: _KT) -> None:
        """Delete item."""
        del self._queue[__key]

    def __iter__(self) -> Iterator[_KT]:
        """Iterate items."""
        return iter(self._queue)

    def __len__(self) -> int:
        """Get the size of the queue."""
        return len(self._queue)

    def __setitem__(self, __key: _KT, __value: _VT) -> None:
        """Set item."""
        self._queue[__key] = __value


class QueueEntity(MutableSequence[_VT]):
    """Representation of an queue for rascal scheduler."""

    __slots__ = ("_queue_entities",)

    _queue_entities: list[_VT]

    def __init__(self, queue_entities: Any) -> None:
        """Initialize a queue entity."""
        if queue_entities is None:
            self._queue_entities = []
        else:
            self._queue_entities = queue_entities

    def __getitem__(self, __key: Any) -> Any:
        """Get item."""
        return self._queue_entities[__key]

    def __delitem__(self, __key: Any) -> Any:
        """Delete item."""
        self._queue_entities.pop(__key)

    def __len__(self) -> int:
        """Get the size of the queue."""
        return len(self._queue_entities)

    def __setitem__(self, __key: Any, __value: Any) -> None:
        """Set item."""
        self._queue_entities[__key] = __value

    def insert(self, __key: Any, __value: Any) -> None:
        """Insert key value pair."""
        self._queue_entities.insert(__key, __value)
