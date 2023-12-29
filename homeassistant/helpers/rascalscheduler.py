"""Helpers to execute rasc entities."""
from __future__ import annotations

from collections.abc import Iterator, MutableMapping, MutableSequence
import json
import logging
import time
from typing import Any, TypeVar

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components.device_automation import action as device_action
from homeassistant.const import CONF_CONTINUE_ON_ERROR
from homeassistant.core import Context, HomeAssistant
from homeassistant.util import slugify

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

_LOGGER = logging.getLogger(__name__)


class RoutineEntity:
    """A class that describes routine entities for Rascal Scheduler."""

    def __init__(
        self,
        name: str | None,
        routine_id: str | None,
        actions: dict[str, ActionEntity],
        timeout: float,
        logger: logging.Logger | None = None,
        log_exceptions: bool = True,
    ) -> None:
        """Initialize a routine entity."""
        self.name = name
        self.routine_id = routine_id
        self.actions = actions
        self._start_time: float | None = None
        self._last_trigger_time: float | None = None
        self._timeout = timeout
        self._set_logger(logger)
        self._log_exceptions = log_exceptions

    @property
    def start_time(self) -> float | None:
        """Return the start time of the routine entity."""
        return self._start_time

    @property
    def last_trigger_time(self) -> float | None:
        """Return the last trigger time or the routine entity."""
        return self._last_trigger_time

    @property
    def timeout(self) -> float:
        """Return the timeout of the routine entity."""
        return self._timeout

    def set_variables(self, var: dict[str, Any]) -> None:
        """Set variables to all the action entities."""
        for entity in self.actions.values():
            entity.variables = var

    def set_context(self, ctx: Context | None) -> None:
        """Set context to all the action entities."""
        for entity in self.actions.values():
            entity.context = ctx

    def _set_logger(self, logger: logging.Logger | None = None) -> None:
        """Set logger."""
        if logger:
            self._logger = logger
        else:
            self._logger = logging.getLogger(f"{__name__}.{slugify(self.name)}")

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

        if self._last_trigger_time is None:
            self._start_time = time.time()
            self._last_trigger_time = self._start_time
        else:
            self._last_trigger_time = self._start_time
            self._start_time = time.time()

        return RoutineEntity(
            self.name, self.routine_id, routine_entity, self._timeout, self._logger
        )

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
        self._log_exceptions = False

    async def attach_triggered(self, log_exceptions: bool) -> None:
        """Trigger the function."""
        action = cv.determine_script_action(self.action)
        continue_on_error = self.action.get(CONF_CONTINUE_ON_ERROR, False)

        try:
            handler = f"_async_{action}_step"
            await getattr(self, handler)()

        except Exception as ex:  # pylint: disable=broad-except
            self._handle_exception(
                ex, continue_on_error, self._log_exceptions or log_exceptions
            )

    async def _async_device_step(self) -> None:
        """Execute device automation."""
        await device_action.async_call_action_from_config(
            self.hass, self.action, self.variables, self.context
        )

    def _handle_exception(
        self, exception: Exception, continue_on_error: bool, log_exceptions: bool
    ) -> None:
        if not isinstance(exception, _HaltScript) and log_exceptions:
            self._log_exception(exception)

        if not continue_on_error:
            raise exception

        # An explicit request to stop the script has been raised.
        if isinstance(exception, _StopScript):
            raise exception

        # These are incorrect scripts, and not runtime errors that need to
        # be handled and thus cannot be stopped by `continue_on_error`.
        if isinstance(
            exception,
            (
                vol.Invalid,
                exceptions.TemplateError,
                exceptions.ServiceNotFound,
                exceptions.InvalidEntityFormatError,
                exceptions.NoEntitySpecifiedError,
                exceptions.ConditionError,
            ),
        ):
            raise exception

        # Only Home Assistant errors can be ignored.
        if not isinstance(exception, exceptions.HomeAssistantError):
            raise exception

    def _log_exception(self, exception: Exception) -> None:
        """Log exception."""
        action_type = cv.determine_script_action(self.action)

        error = str(exception)

        if isinstance(exception, vol.Invalid):
            error_desc = "Invalid data"

        elif isinstance(exception, exceptions.TemplateError):
            error_desc = "Error rendering template"

        elif isinstance(exception, exceptions.Unauthorized):
            error_desc = "Unauthorized"

        elif isinstance(exception, exceptions.ServiceNotFound):
            error_desc = "Service not found"

        elif isinstance(exception, exceptions.HomeAssistantError):
            error_desc = "Error"

        else:
            error_desc = "Unexpected error"

        _LOGGER.warning(
            "Error executing script. %s for %s at action_id %s: %s",
            error_desc,
            action_type,
            self.action_id,
            error,
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


class _HaltScript(Exception):
    """Throw if script needs to stop executing."""


class _StopScript(_HaltScript):
    """Throw if script needs to stop."""

    def __init__(self, message: str, response: Any) -> None:
        """Initialize a halt exception."""
        super().__init__(message)
        self.response = response
