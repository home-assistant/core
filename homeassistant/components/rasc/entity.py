"""Helpers to execute rasc entities."""
from __future__ import annotations

import asyncio
from collections.abc import Iterator, Sequence
from contextlib import suppress
from datetime import timedelta
import json
import logging
import re
import shortuuid
import time
from typing import Any, Generic, TypeVar

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components.device_automation import action as device_action
from homeassistant.const import (
    ATTR_ACTION_ID,
    CONF_CONTINUE_ON_ERROR,
    CONF_ENTITY_ID,
    CONF_RESPONSE_VARIABLE,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    service,
)
from homeassistant.util import slugify

from .const import CONF_TRANSITION

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_T = TypeVar("_T")

_LOGGER = logging.getLogger(__name__)
_LOG_EXCEPTION = logging.ERROR + 1

TIMEOUT = 3000  # millisecond
TIME_MILLISECOND = 1000


CONF_END_VIRTUAL_NODE = "end_virtual_node"
CONF_ENTITY_REGISTRY = "entity_registry"


def get_device_id_from_entity_id(hass: HomeAssistant, entity_id: str) -> str:
    """Get device ID from an entity ID.

    Raises ValueError if entity or device ID is invalid.
    """
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get(entity_id)

    if entity_entry is None or entity_entry.device_id is None:
        raise ValueError(f"Entity {entity_id} is not a valid entity.")

    return str(entity_entry.device_id)


def get_entity_id_from_number(hass: HomeAssistant, entity_id: str) -> str:
    """Get entity_id from number."""
    pattern = re.compile("^[^.]+[.][^.]+$")
    if not pattern.match(entity_id):
        registry: er.EntityRegistry = hass.data[CONF_ENTITY_REGISTRY]
        entity_entry = registry.async_get(entity_id)
        if not entity_entry or entity_entry.device_id is None:
            raise ValueError(f"Entity {entity_id} is not a valid entity.")
        return str(entity_entry.as_partial_dict[CONF_ENTITY_ID])

    return str(entity_id)


def generate_short_uuid(size: int = 5) -> str:
    """Generate short uuid."""
    return shortuuid.ShortUUID().random(length=size)


class BaseRoutineEntity:
    """A class that describes routine entities for Rascal Scheduler."""

    def __init__(
        self,
        name: str | None,
        routine_id: str,
        actions: dict[str, ActionEntity],
        action_script: Sequence[dict[str, Any]],
        timeout: float = 20.0,
    ) -> None:
        """Initialize a routine entity."""
        self._name = name
        self._routine_id = routine_id
        self.actions = actions
        self.action_script = action_script
        self._start_time: float | None = None
        self._last_trigger_time: float | None = None
        self._timeout = timeout

    @property
    def name(self) -> str | None:
        """Get name."""
        return self._name

    def duplicate(self, var: dict[str, Any], ctx: Context | None) -> RoutineEntity:
        """Duplicate the routine entity. Only the base routine can call this function."""

        new_routine_id = self._routine_id + "-" + generate_short_uuid()

        routine_entity = dict[str, ActionEntity]()

        for action_id, entity in self.actions.items():
            if not entity.is_end_node:
                new_action_id = new_routine_id + "." + action_id.split(".")[1]
                routine_entity[new_action_id] = ActionEntity(
                    hass=entity.hass,
                    action=entity.action,
                    action_id=new_action_id,
                    duration=entity.duration,
                    delay=entity.delay,
                    variables=var,
                    context=ctx,
                    logger=entity.logger,
                )

            else:
                routine_entity[CONF_END_VIRTUAL_NODE] = ActionEntity(
                    hass=entity.hass,
                    action={},
                    action_id="",
                    duration=entity.duration,
                    is_end_node=True,
                    logger=entity.logger,
                )

        for action_id, entity in self.actions.items():
            if not entity.is_end_node:
                new_action_id = new_routine_id + "." + action_id.split(".")[1]

                for parent in entity.parents:
                    new_parent_action_id = (
                        new_routine_id + "." + parent.action_id.split(".")[1]
                    )
                    routine_entity[new_action_id].parents.append(
                        routine_entity[new_parent_action_id]
                    )

                for child in entity.children:
                    if not child.is_end_node:
                        new_child_action_id = (
                            new_routine_id + "." + child.action_id.split(".")[1]
                        )

                        routine_entity[new_action_id].children.append(
                            routine_entity[new_child_action_id]
                        )
                    else:
                        routine_entity[new_action_id].children.append(
                            routine_entity[CONF_END_VIRTUAL_NODE]
                        )
            else:
                for parent in entity.parents:
                    new_parent_action_id = (
                        new_routine_id + "." + parent.action_id.split(".")[1]
                    )
                    routine_entity[CONF_END_VIRTUAL_NODE].parents.append(
                        routine_entity[new_parent_action_id]
                    )

        if not self._last_trigger_time:
            self._start_time = time.time()
            self._last_trigger_time = self._start_time
        else:
            self._last_trigger_time = self._start_time
            self._start_time = time.time()

        # self.output(new_routine_id, routine_entity)

        return RoutineEntity(
            name=self._name,
            routine_id=new_routine_id,
            actions=routine_entity,
            action_script=self.action_script,
            start_time=self._start_time,
            last_trigger_time=self._last_trigger_time,
            logger=_LOGGER,
        )

    def abort_if_within_timeout(self) -> bool:
        """Abort if the same routine is trigger frequently."""
        if not self._last_trigger_time:
            return False

        return time.time() - self._last_trigger_time < self._timeout

    def output(self, routine_id: str, actions: dict[str, Any]) -> None:
        """Print the routine information."""
        action_list = []
        for _, entity in actions.items():
            parents = []
            children = []

            for parent in entity.parents:
                parents.append(parent.action_id)

            for child in entity.children:
                children.append(child.action_id)

            entity_json = {
                "action_id": entity.action_id,
                "action": entity.action,
                "action_completed": entity.action_completed,
                "parents": parents,
                "children": children,
                "delay": str(entity.delay),
                "duration": str(entity.duration),
            }

            action_list.append(entity_json)

        out = {"routine_id": routine_id, "actions": action_list}

        print(json.dumps(out, indent=2))  # noqa: T201


class RoutineEntity(BaseRoutineEntity):
    """Routine Entity."""

    def __init__(
        self,
        name: str | None,
        routine_id: str,
        actions: dict[str, ActionEntity],
        action_script: Sequence[dict[str, Any]],
        start_time: float | None = None,
        last_trigger_time: float | None = None,
        logger: logging.Logger | None = None,
        log_exceptions: bool = True,
    ) -> None:
        """Initialize a routine entity."""
        super().__init__(name, routine_id, actions, action_script)
        self._start_time = start_time
        self._last_trigger_time = last_trigger_time
        self._set_logger(logger)
        self._log_exceptions = log_exceptions
        self._attr_earliest_end_time: str

    @property
    def routine_id(self) -> str:
        """Get routine id."""
        return self._routine_id

    @property
    def start_time(self) -> float | None:
        """Get start time."""
        return self._start_time

    def _set_logger(self, logger: logging.Logger | None = None) -> None:
        """Set logger."""
        if logger:
            self._logger = logger
        else:
            self._logger = logging.getLogger(f"{__name__}.{slugify(self.name)}")

    @property
    def earliest_end_time(self) -> str:
        """Get earliest end time."""
        return self._attr_earliest_end_time

    @earliest_end_time.setter
    def earliest_end_time(self, end_time: str) -> None:
        """Set earliest end time."""
        self._attr_earliest_end_time = end_time


class ActionEntity:
    """Action Entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        action: dict[str, Any],
        action_id: str,
        duration: timedelta,
        is_end_node: bool = False,
        delay: timedelta | None = None,
        variables: dict[str, Any] | None = None,
        context: Context | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize a routine entity."""
        self.hass = hass
        self.action = action
        self._action_id = action_id
        self.action_acked = False
        self.action_started = False
        self.action_completed = False
        self.parents: list[ActionEntity] = []
        self.children: list[ActionEntity] = []
        self.duration = duration
        self.delay = delay
        self.variables = variables
        self.context = context
        self._log_exceptions = False
        self._set_logger(logger)
        self._stop = asyncio.Event()
        self._attr_is_end_node = is_end_node

    @property
    def action_id(self) -> str:
        """Get action id."""
        return self._action_id

    @property
    def service(self) -> str | None:
        """Get service."""
        return self.action.get(CONF_SERVICE, None)

    @property
    def service_data(self) -> dict[str, Any] | None:
        """Get service data."""
        return self.action.get(CONF_SERVICE_DATA, None)

    @property
    def transition(self) -> float | None:
        """Get transition."""
        if self.service_data is None or CONF_TRANSITION not in self.service_data:
            return None
        return self.service_data.get(CONF_TRANSITION, None)

    @property
    def is_end_node(self) -> bool:
        """Get is_end_node attribute."""
        return self._attr_is_end_node

    @property
    def logger(self) -> logging.Logger | None:
        """Get logger."""
        return self._logger

    @property
    def duplicate(self) -> ActionEntity:
        """Duplicate the action entity."""
        new_entity = ActionEntity(
            hass=self.hass,
            action=self.action,
            action_id=self._action_id,
            duration=self.duration,
        )
        new_entity.parents = self.parents
        new_entity.children = self.children
        return new_entity

    def _set_logger(self, logger: logging.Logger | None = None) -> None:
        """Set logger."""
        self._logger = logger

    def _step_log(self, default_message: Any, timeout: Any = None) -> None:
        """Step log."""
        _timeout = (
            "" if timeout is None else f" (timeout: {timedelta(seconds=timeout)})"
        )
        self._log(
            "Executing step %s%s", default_message, _timeout
        )  # pylint: disable=protected-access

    def _log(
        self, msg: str, *args: Any, level: int = logging.INFO, **kwargs: Any
    ) -> None:
        """Log."""
        msg = f"%s: {msg}"
        args = (str(self.action_id), *args)

        if self._logger is not None:
            if level == _LOG_EXCEPTION:
                self._logger.exception(msg, *args, **kwargs)
            else:
                self._logger.log(level, msg, *args, **kwargs)

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

        self.action[CONF_ENTITY_ID] = get_entity_id_from_number(
            self.hass, self.action[CONF_ENTITY_ID]
        )

        if self._action_id:
            if not self.variables:
                self.variables = {}
            self.variables[ATTR_ACTION_ID] = self._action_id

        if self.variables and self.context is not None:
            await device_action.async_call_action_from_config(
                self.hass, self.action, self.variables, self.context
            )

    async def async_delay_step(self) -> None:
        """Handle delay."""
        await self._async_delay_step()

    async def _async_delay_step(self) -> None:
        """Handle delay."""
        if self.delay is not None:
            delay = self.delay
            self._step_log(f"delay {delay}")

            try:
                async with asyncio.timeout(delay.total_seconds()):
                    await self._stop.wait()
            except asyncio.TimeoutError:
                self._step_log("delay completed")

    async def _async_call_service_step(self) -> None:
        """Call the service specified in the action."""
        self._step_log("call service")
        if self.variables is not None:
            params = service.async_prepare_call_from_config(
                self.hass, self.action, self.variables
            )

            params["service_data"]["action_id"] = self._action_id
            # Validate response data parameters. This check ignores services that do
            # not exist which will raise an appropriate error in the service call below.
            response_variable = self.action.get(CONF_RESPONSE_VARIABLE)

            return_response = response_variable is not None

            response_data = await self._async_run_long_action(
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        **params,
                        blocking=True,
                        context=self.context,
                        return_response=return_response,
                    )
                ),
            )
            if response_variable:
                self.variables[response_variable] = response_data

    async def _async_run_long_action(self, long_task: asyncio.Task[_T]) -> _T | None:
        """Run a long task while monitoring for stop request."""

        async def async_cancel_long_task() -> None:
            # Stop long task and wait for it to finish.
            long_task.cancel()
            with suppress(Exception):
                await long_task

        # Wait for long task while monitoring for a stop request.
        stop_task = self.hass.async_create_task(self._stop.wait())
        try:
            await asyncio.wait(
                {long_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
        # If our task is cancelled, then cancel long task, too. Note that if long task
        # is cancelled otherwise the CancelledError exception will not be raised to
        # here due to the call to asyncio.wait(). Rather we'll check for that below.
        except asyncio.CancelledError:
            await async_cancel_long_task()
            raise
        finally:
            stop_task.cancel()

        if long_task.cancelled():
            raise asyncio.CancelledError
        if long_task.done():
            # Propagate any exceptions that occurred.
            return long_task.result()
        # Stopped before long task completed, so cancel it.
        await async_cancel_long_task()
        return None

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


class Queue(Generic[_KT, _VT]):
    """Representation of a queue for a scheduler with order maintenance."""

    __slots__ = ("_keys", "_data")

    _keys: list[_KT]
    _data: dict[_KT, _VT | None]

    def __init__(
        self, queue: dict[_KT, _VT | None] | Queue[_KT, _VT] | None = None
    ) -> None:
        """Initialize a queue entity."""
        self._data = {}
        self._keys = []
        if queue:
            if hasattr(queue, "items"):
                for key, value in queue.items():
                    self._keys.append(key)
                    self._data[key] = value
            else:
                raise TypeError(
                    "The provided queue does not support items() method and cannot be treated as a mapping"
                )

    def __getitem__(self, key: _KT) -> _VT | None:
        """Get item."""
        return self._data[key]

    def __setitem__(self, key: _KT, value: _VT | None) -> None:
        """Set item."""
        self._keys.append(key)
        self._data[key] = value

    def __delitem__(self, key: _KT) -> None:
        """Delete item."""
        del self._data[key]
        self._keys.remove(key)

    def __iter__(self) -> Iterator[_KT]:
        """Iterate keys."""
        return iter(self._keys)

    def __len__(self) -> int:
        """Get the size of the queue."""
        return len(self._keys)

    def __contains__(self, key: object) -> bool:
        """Check if the key contains in the queue."""
        return key in self._keys if isinstance(key, str) else False

    def keys(self) -> Iterator[_KT]:
        """Get keys."""
        yield from self._keys

    def items(self) -> Iterator[tuple[_KT, _VT | None]]:
        """Get keys and values."""
        for key in self._keys:
            yield key, self._data[key]

    def values(self) -> Iterator[_VT | None]:
        """Get values."""
        for key in self._keys:
            yield self._data[key]

    def get(self, key: _KT, default=None) -> _VT | None:
        """Get the value with the key."""
        try:
            return self._data[key]
        except KeyError:
            return default

    def getitem(self, index: int) -> _VT | None:
        """Get item in the index position."""
        try:
            key = self._keys[index]
            return self._data[key]
        except KeyError as e:
            raise KeyError("Key does not found while doing getitem.") from e

    def pop(self, key: _KT, default=None) -> _VT | None:
        """Pop the value according to the key."""
        value = self.get(key, default)
        del self._data[key]
        self._keys.remove(key)

        return value

    def clear(self) -> None:
        """Clean the queue."""
        self._keys = []
        self._data = {}

    def update(self, queue: Queue[_KT, _VT]) -> None:
        """Extend the queue."""
        for key, value in queue.items():
            self._keys.append(key)
            self._data[key] = value

    def updateitem(self, key: _KT, value: _VT | None) -> None:
        """Update the item."""
        try:
            self._data[key] = value
        except KeyError as e:
            raise KeyError("Key does not found while updating item.") from e

    def setdefault(self, key: _KT, default: _VT | None) -> _VT | None:
        """Return the value of the item with the specified key. If the key does not exist, insert the key with the specified value."""
        try:
            return self[key]
        except KeyError:
            self[key] = default
            return self[key]

    def top(self) -> tuple[_KT, _VT | None] | tuple[None, None]:
        """Get the first item in the queue."""
        if not self._keys:
            return None, None

        key = self._keys[0]
        value = self._data[key]
        return key, value

    def end(self) -> tuple[_KT, _VT | None] | tuple[None, None]:
        """Get the last element in the queue."""
        if not self._keys:
            return None, None

        key = self._keys[-1]
        value = self._data[key]
        return key, value

    def insert_before(self, key: _KT, new_key: _KT, value: _VT | None) -> None:
        """Insert the new_key before the key with the value."""
        try:
            self._keys.insert(self._keys.index(key), new_key)
            self._data[new_key] = value
        except ValueError:
            raise KeyError(key) from ValueError

    def insert_after(self, key: _KT, new_key: _KT, value: _VT | None) -> None:
        """Insert the new_key after the key with the value."""
        try:
            self._keys.insert(self._keys.index(key) + 1, new_key)
            self._data[new_key] = value
        except ValueError:
            raise KeyError(key) from ValueError

    def index(self, key: _KT) -> int:
        """Return the index of the key."""
        try:
            return self._keys.index(key)
        except Exception as e:
            raise KeyError("An error occurred while getting the key index.") from e

    def next(self, key: _KT | None) -> _VT | None:
        """Return the next item with the key."""
        if key is None:
            return None
        index = self._keys.index(key)
        if index + 1 < len(self._keys):
            key = self._keys[index + 1]
            return self._data[key]
        return None

    def nextitem(self, index: int) -> _VT | None:
        """Return the next item with the index."""
        if index + 1 < len(self._keys):
            key = self._keys[index + 1]
            return self._data[key]
        return None

    def prev(self, key: _KT) -> _VT | None:
        """Return the previous item with the key."""
        index = self._keys.index(key)
        if index - 1 >= 0:
            key = self._keys[index - 1]
            return self._data[key]
        return None


class _HaltScript(Exception):
    """Throw if script needs to stop executing."""


class _StopScript(_HaltScript):
    """Throw if script needs to stop."""

    def __init__(self, message: str, response: Any) -> None:
        """Initialize a halt exception."""
        super().__init__(message)
        self.response = response

    # def timeout(self)->bool:
    #     """Check if the routine exceeds the timeout."""
    #     now = time.time()
    #     last_trigger_time = self._last_trigger_time
    #     timeout = self._timeout

    #     if last_trigger_time is None or (now - last_trigger_time) * TIME_MILLISECOND > timeout:
    #         return False

    #     return True
