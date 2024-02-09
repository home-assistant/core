"""Helpers to execute rasc entities."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Iterator
from contextlib import suppress
from datetime import timedelta
import json
import logging
import time
from typing import Any, TypeVar

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components.device_automation import action as device_action
from homeassistant.const import (
    CONF_CONTINUE_ON_ERROR,
    CONF_ENTITY_ID,
    CONF_RESPONSE_VARIABLE,
    RASC_SCHEDULED,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.rascalscheduler import async_get_entity_id_from_number
from homeassistant.util import slugify

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")
_T = TypeVar("_T")

_LOGGER = logging.getLogger(__name__)
_LOG_EXCEPTION = logging.ERROR + 1

TIMEOUT = 3000  # millisecond
TIME_MILLISECOND = 1000

CONF_END_VIRTUAL_NODE = "end_virtual_node"


class BaseRoutineEntity:
    """A class that describes routine entities for Rascal Scheduler."""

    def __init__(
        self,
        name: str | None,
        routine_id: str | None,
        actions: dict[str, ActionEntity],
        # timeout: float,
    ) -> None:
        """Initialize a routine entity."""
        self._name = name
        self._routine_id = routine_id
        self.actions = actions
        # self._timeout = timeout
        self._start_time: float | None = None
        self._last_trigger_time: float | None = None

    # def timeout(self)->bool:
    #     """Check if the routine exceeds the timeout."""
    #     now = time.time()
    #     last_trigger_time = self._last_trigger_time
    #     timeout = self._timeout

    #     if last_trigger_time is None or (now - last_trigger_time) * TIME_MILLISECOND > timeout:
    #         return False

    #     return True

    @property
    def name(self) -> str | None:
        """Get name."""
        return self._name

    def duplicate(
        self, var: dict[str, Any] | None, ctx: Context | None
    ) -> RoutineEntity:
        """Duplicate the routine entity. Only the base routine can call this function."""

        routine_entity = {}

        for action_id, entity in self.actions.items():
            if action_id is not None:
                routine_entity[action_id] = ActionEntity(
                    hass=entity.hass,
                    action=entity.action,
                    action_id=entity.action_id,
                    action_state=RASC_SCHEDULED,
                    routine_id=entity.routine_id,
                    delay=entity.delay,
                    group=entity.group,
                    variables=var,
                    context=ctx,
                    logger=entity.logger,
                )

            else:
                routine_entity[CONF_END_VIRTUAL_NODE] = ActionEntity(
                    hass=entity.hass,
                    action={},
                    action_id=None,
                    action_state=None,
                    routine_id=entity.routine_id,
                    logger=entity.logger,
                )

        for action_id, entity in self.actions.items():
            if action_id is not None:
                for parent in entity.parents:
                    if parent.action_id is not None:
                        routine_entity[action_id].parents.append(
                            routine_entity[parent.action_id]
                        )

                for child in entity.children:
                    if child.action_id is not None:
                        routine_entity[action_id].children.append(
                            routine_entity[child.action_id]
                        )
                    else:
                        routine_entity[action_id].children.append(
                            routine_entity[CONF_END_VIRTUAL_NODE]
                        )
            else:
                for parent in entity.parents:
                    if parent.action_id is not None:
                        routine_entity[CONF_END_VIRTUAL_NODE].parents.append(
                            routine_entity[parent.action_id]
                        )

        if self._last_trigger_time is None:
            self._start_time = time.time()
            self._last_trigger_time = self._start_time
        else:
            self._last_trigger_time = self._start_time
            self._start_time = time.time()

        return RoutineEntity(
            name=self._name,
            routine_id=self._routine_id,
            actions=routine_entity,
            start_time=self._start_time,
            last_trigger_time=self._last_trigger_time,
            logger=_LOGGER,
        )

    def output(self) -> None:
        """Print the routine information."""
        actions = []
        for _, entity in self.actions.items():
            parents = []
            children = []

            for parent in entity.parents:
                parents.append(parent.action_id)

            for child in entity.children:
                children.append(child.action_id)

            entity_json = {
                "action_id": entity.action_id,
                "action": entity.action,
                "action state": entity.action_state,
                "parents": parents,
                "children": children,
                "delay": str(entity.delay),
            }

            actions.append(entity_json)

        out = {"routine_id": self._routine_id, "actions": actions}

        print(json.dumps(out, indent=2))  # noqa: T201


class RoutineEntity(BaseRoutineEntity):
    """Routine Entity."""

    def __init__(
        self,
        name: str | None,
        routine_id: str | None,
        actions: dict[str, ActionEntity],
        timeout: float | None = None,
        start_time: float | None = None,
        last_trigger_time: float | None = None,
        logger: logging.Logger | None = None,
        log_exceptions: bool = True,
    ) -> None:
        """Initialize a routine entity."""
        super().__init__(name, routine_id, actions)
        self._start_time = start_time
        self._last_trigger_time = last_trigger_time
        self._set_logger(logger)
        self._log_exceptions = log_exceptions

    @property
    def routine_id(self) -> str | None:
        """Get routine id."""
        return self._routine_id

    def _set_logger(self, logger: logging.Logger | None = None) -> None:
        """Set logger."""
        if logger:
            self._logger = logger
        else:
            self._logger = logging.getLogger(f"{__name__}.{slugify(self.name)}")


class ActionEntity:
    """Action Entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        action: dict[str, Any],
        action_id: str | None,
        action_state: str | None,
        routine_id: str | None,
        delay: timedelta | None = None,
        group: bool = False,
        variables: dict[str, Any] | None = None,
        context: Context | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize a routine entity."""
        self.hass = hass
        self.action = action
        self._action_id = action_id
        self._action_state = action_state
        self._routine_id = routine_id
        self.parents: list[ActionEntity] = []
        self.children: list[ActionEntity] = []
        self.delay = delay
        self.group = group
        self.variables = variables
        self.context = context
        self._log_exceptions = False
        self._set_logger(logger)
        self._stop = asyncio.Event()

    @property
    def action_id(self) -> str | None:
        """Get action id."""
        return self._action_id

    @property
    def routine_id(self) -> str | None:
        """Get routine id."""
        return self._routine_id

    @property
    def action_state(self) -> str | None:
        """Get action state."""
        return self._action_state

    @action_state.setter
    def action_state(self, state: str) -> None:
        """Set action state."""
        self._action_state = state

    @property
    def logger(self) -> logging.Logger | None:
        """Get logger."""
        return self._logger

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

        self.action[CONF_ENTITY_ID] = async_get_entity_id_from_number(
            self.hass, self.action[CONF_ENTITY_ID]
        )
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


class Queue(OrderedDict[_KT, _VT]):
    """Representation of a queue for a scheduler with order maintenance."""

    __slots__ = ("_queue",)

    _queue: OrderedDict[_KT, _VT]

    def __init__(self, queue: Any = None) -> None:
        """Initialize a queue entity."""
        self._queue = OrderedDict() if queue is None else OrderedDict(queue)

    def __getitem__(self, key: _KT) -> _VT:
        """Get item."""
        return self._queue[key]

    def __setitem__(self, key: _KT, value: _VT) -> None:
        """Set item."""
        self._queue[key] = value

    def __delitem__(self, key: _KT) -> None:
        """Delete item."""
        del self._queue[key]

    def __iter__(self) -> Iterator[_KT]:
        """Iterate items."""
        return iter(self._queue)

    def __len__(self) -> int:
        """Get the size of the queue."""
        return len(self._queue)

    def next(self):
        """Get the first key (action_id) and its corresponding value (action_state) in the OrderedDict."""
        if self._queue:
            key, value = next(iter(self._queue))
            return key, value
        return None, None


class _HaltScript(Exception):
    """Throw if script needs to stop executing."""


class _StopScript(_HaltScript):
    """Throw if script needs to stop."""

    def __init__(self, message: str, response: Any) -> None:
        """Initialize a halt exception."""
        super().__init__(message)
        self.response = response
