"""Helpers to execute rasc entities."""
from __future__ import annotations

from collections.abc import Iterator, MutableMapping, MutableSequence
import json
import time
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

RASC_SCHEDULED = "scheduled"
RASC_START = "start"
RASC_COMPLETE = "complete"
RASC_RESPONSE = "rasc_response"


class BaseRoutineEntity:
    """A class of base routine entity."""

    counters: dict[str, int] = {}
    routine_start_times: dict[str, float] = {}

    @classmethod
    def add_counter(cls, routine_id: str) -> None:
        """Increment counter by 1."""
        cls.counters[routine_id] = cls.counters[routine_id] + 1

    @classmethod
    def get_counter(cls, routine_id: str) -> int:
        """Return counter based on the routine_id."""
        return cls.counters[routine_id]

    @classmethod
    def set_counter(cls, routine_id: str, counter: int) -> None:
        """Set the counter."""
        cls.counters[routine_id] = counter

    @classmethod
    def get_start_time(cls, routine_id: str) -> float:
        """Return the start time based on the routine_id."""
        return cls.routine_start_times[routine_id]

    @classmethod
    def set_start_time(cls, routine_id: str, st: float) -> None:
        """Set the start time."""
        cls.routine_start_times[routine_id] = st


class RoutineEntity(BaseRoutineEntity):
    """A class that describes routine entities for Rascal Scheduler."""

    def __init__(
        self,
        routine_id: str,
        actions: dict[str, ActionEntity],
    ) -> None:
        """Initialize a routine entity."""

        self.routine_id = routine_id
        self._instance_id: str
        self.actions = actions
        self._start_time: float
        self._timeout: int = 3

    @property
    def instance_id(self) -> str:
        """Get instante_id."""
        return self._instance_id

    @property
    def timeout(self) -> float:
        """Get timeout."""
        return self._timeout

    def set_variables(self, var: dict[str, Any]) -> None:
        """Set variables to all the action entities."""
        for entity in self.actions.values():
            entity.variables = var

    def set_context(self, ctx: Context | None) -> None:
        """Set context to all the action entities."""
        for entity in self.actions.values():
            entity.context = ctx

    def duplicate(self) -> RoutineEntity:
        """Duplicate the routine entity."""
        routine_entity = {}

        for action_id, entity in self.actions.items():
            routine_entity[action_id] = ActionEntity(
                hass=entity.hass,
                action=entity.action,
                action_id=entity.action_id,
                action_state=None,
                routine_id=entity.routine_id,
            )

        for action_id, entity in self.actions.items():
            for parent in entity.parents:
                routine_entity[action_id].parents.append(
                    routine_entity[parent.action_id]
                )

            for child in entity.children:
                routine_entity[action_id].children.append(
                    routine_entity[child.action_id]
                )

        RoutineEntity.add_counter(self.routine_id)
        RoutineEntity.set_start_time(self.routine_id, time.time())
        self._instance_id = str(RoutineEntity.get_counter(self.routine_id))
        self._start_time = time.time()

        return RoutineEntity(self.routine_id, routine_entity)

    def output(self) -> None:
        """Print the routine information."""
        actions = []
        for action_id, entity in self.actions.items():
            parents = []
            children = []

            for parent in entity.parents:
                parents.append(parent.action_id)

            for child in entity.children:
                children.append(child.action_id)

            entity_json = {
                "action_id": action_id,
                "action": entity.action,
                "state": entity.action_state,
                "parents": parents,
                "children": children,
            }

            actions.append(entity_json)

        out = {"routine_id": self.routine_id, "actions": actions}

        print(json.dumps(out, indent=2))  # noqa: T201


class ActionEntity:
    """Initialize a routine entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        action: dict[str, Any],
        action_id: str,
        action_state: str | None,
        routine_id: str | None,
    ) -> None:
        """Initialize a routine entity."""
        self.hass = hass
        self.action = action
        self.action_id = action_id

        if action_state is None:
            self.action_state = RASC_SCHEDULED
        else:
            self.action_state = action_state

        self.parents: list[ActionEntity] = []
        self.children: list[ActionEntity] = []
        self.routine_id = routine_id
        self.variables: dict[str, Any]
        self.context: Context | None

    async def attach_triggered(self) -> None:
        """Trigger the function."""
        # print("[rascal] attach_triggered")
        action = cv.determine_script_action(self.action)

        try:
            handler = f"_async_{action}_step"
            await getattr(self, handler)()

        except Exception:  # pylint: disable=broad-except
            return
            # print(ex)

    async def _async_device_step(self) -> None:
        """Execute device automation."""
        await device_action.async_call_action_from_config(
            self.hass, self.action, self.variables, self.context
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

    def empty(self) -> bool:
        """Return empty."""
        return len(self._queue_entities) == 0

    def append(self, __value: Any) -> None:
        """Append new value."""
        self._queue_entities.append(__value)
