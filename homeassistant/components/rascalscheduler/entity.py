"""Helpers to execute rasc entities."""
# from __future__ import annotations

# import asyncio
# from collections.abc import Iterator, MutableSequence, Sequence
# from collections import OrderedDict
# from contextlib import suppress
# from datetime import timedelta
# import json, logging, time, re
# from typing import Any, TypeVar

# import voluptuous as vol
# from homeassistant.components.script import BaseScriptEntity
# from homeassistant import exceptions
# from homeassistant.components.device_automation import action as device_action
# from homeassistant.const import (
#     CONF_CONTINUE_ON_ERROR,
#     CONF_RESPONSE_VARIABLE,
#     CONF_TARGET,
#     CONF_DEVICE_ID,
#     CONF_ENTITY_ID,
#     CONF_SERVICE,
#     CONF_DELAY,
#     CONF_PARALLEL,
#     CONF_SEQUENCE,
#     DOMAIN_AUTOMATION,
#     DOMAIN_PERSON,
#     DOMAIN_RASCALSCHEDULER,
#     DOMAIN_SCRIPT,
#     DOMAIN_TTS,
#     DOMAIN_ZONE,
#     NAME_SUN_NEXT_DAWN,
#     NAME_SUN_NEXT_DUSK,
#     NAME_SUN_NEXT_MIDNIGHT,
#     NAME_SUN_NEXT_NOON,
#     NAME_SUN_NEXT_RISING,
#     NAME_SUN_NEXT_SETTING,
#     RASC_SCHEDULED,
#     LOCK_STATE_SCHEDULED
# )
# from homeassistant.core import Context, HomeAssistant
# from homeassistant.util import slugify
# from homeassistant.helpers.template import device_entities

# from . import config_validation as cv, entity_registry as er, service

# _KT = TypeVar("_KT")
# _VT = TypeVar("_VT")
# _T = TypeVar("_T")

# _LOGGER = logging.getLogger(__name__)
# _LOG_EXCEPTION = logging.ERROR + 1

# TIMEOUT = 3000  # millisecond

# CONF_ROUTINE_ID = "routine_id"
# CONF_STEP = "step"
# CONF_HASS = "hass"
# CONF_ENTITY_REGISTRY = "entity_registry"
# CONF_LOGGER = "logger"
# CONF_END_VIRTUAL_NODE = "end_virtual_node"


# def create_routine(
#     hass: HomeAssistant,
#     name: str | None,
#     routine_id: str | None,
#     action_script: Sequence[dict[str, Any]],
# ) -> RoutineEntity:
#     """Convert the script to the DAG using dsf algorithm."""
#     next_parents: list[ActionEntity] = []
#     entities: dict[str, ActionEntity] = {}
#     config: dict[str, Any] = {}

#     # configuration for each node
#     config[CONF_STEP] = -1
#     config[CONF_ROUTINE_ID] = routine_id

#     for _, script in enumerate(action_script):
#         # print("script:", script)
#         if (
#             CONF_PARALLEL not in script
#             and CONF_SEQUENCE not in script
#             and CONF_SERVICE not in script
#             and CONF_DELAY not in script
#         ):
#             # print("script:", script)
#             config[CONF_STEP] = config[CONF_STEP] + 1
#             action_id = config[CONF_ROUTINE_ID] + str(config[CONF_STEP])

#             entities[action_id] = ActionEntity(
#                 hass=hass,
#                 action=script,
#                 action_id=action_id,
#                 action_state=None,
#                 lock_state=None,
#                 routine_id=config[CONF_ROUTINE_ID],
#                 logger=_LOGGER,
#             )

#             for entity in next_parents:
#                 entities[action_id].parents.append(entity)

#             for entity in next_parents:
#                 entity.children.append(entities[action_id])

#             next_parents.clear()
#             next_parents.append(entities[action_id])

#         else:
#             leaf_nodes = dfs(hass, script, config, next_parents, entities)
#             next_parents.clear()
#             next_parents = leaf_nodes

#     # add virtual node to the end of the routine
#     # the use of the virtual node is to identify if all actions in the routine are completed
#     entities["end_virtual_node"] = ActionEntity(
#         hass=hass,
#         action={},
#         action_id=None,
#         action_state=None,
#         lock_state=None,
#         routine_id=config[CONF_ROUTINE_ID],
#         logger=_LOGGER,
#     )

#     for parent in next_parents:
#         parent.children.append(entities["end_virtual_node"])
#         entities["end_virtual_node"].parents.append(parent)

#     return RoutineEntity(name, routine_id, entities, TIMEOUT, _LOGGER)


# def dfs(
#     hass: HomeAssistant,
#     script: dict[str, Any],
#     config: dict[str, Any],
#     parents: list[ActionEntity],
#     entities: dict[str, Any],
# ) -> list[ActionEntity]:
#     """Convert the script to the dag using dsf."""

#     next_parents = []
#     # print("script:", script)
#     if CONF_PARALLEL in script:
#         for item in list(script.values())[0]:
#             leaf_entities = dfs(hass, item, config, parents, entities)
#             for entity in leaf_entities:
#                 next_parents.append(entity)

#     elif CONF_SEQUENCE in script:
#         next_parents = parents
#         for item in list(script.values())[0]:
#             leaf_entities = dfs(hass, item, config, next_parents, entities)
#             next_parents = leaf_entities

#     elif CONF_SERVICE in script:
#         domain = script["service"].split(".")[0]
#         if domain == DOMAIN_SCRIPT:
#             script_component: EntityComponent[BaseScriptEntity] = config[
#                 CONF_HASS
#             ].data[DOMAIN_SCRIPT]

#             if script_component is not None:
#                 base_script = script_component.get_entity(list(script.values())[0])
#                 if base_script is not None and base_script.raw_config is not None:
#                     next_parents = parents
#                     for item in base_script.raw_config[CONF_SEQUENCE]:
#                         leaf_entities = dfs(hass, item, config, next_parents, entities)
#                         next_parents = leaf_entities
#         else:
#             target_entities: list[str] = []
#             if CONF_DEVICE_ID in script[CONF_TARGET]:
#                 device_ids = []
#                 if isinstance(script[CONF_TARGET][CONF_DEVICE_ID], str):
#                     device_ids = [script[CONF_TARGET][CONF_DEVICE_ID]]
#                 else:
#                     device_ids = script[CONF_TARGET][CONF_DEVICE_ID]
#                 target_entities += [
#                     entity
#                     for device_id in device_ids
#                     for entity in device_entities(hass, device_id)
#                 ]

#             if CONF_ENTITY_ID in script[CONF_TARGET]:
#                 if isinstance(script[CONF_TARGET][CONF_ENTITY_ID], str):
#                     target_entities += [script[CONF_TARGET][CONF_ENTITY_ID]]
#                 else:
#                     target_entities += script[CONF_TARGET][CONF_ENTITY_ID]

#             config[CONF_STEP] = config[CONF_STEP] + 1
#             action_id = config[CONF_ROUTINE_ID] + str(config[CONF_STEP])

#             entities[action_id] = ActionEntity(
#                 hass=hass,
#                 action=script,
#                 action_id=action_id,
#                 action_state=None,
#                 lock_state=None,
#                 routine_id=config[CONF_ROUTINE_ID],
#                 group=len(target_entities) > 1,
#                 logger=_LOGGER,
#             )

#             for entity in parents:
#                 entities[action_id].parents.append(entity)
#                 entity.children.append(entities[action_id])

#             next_parents.append(entities[action_id])
#     elif CONF_DELAY in script:
#         hours = script[CONF_DELAY]["hours"]
#         minutes = script[CONF_DELAY]["minutes"]
#         seconds = script[CONF_DELAY]["seconds"]
#         milliseconds = script[CONF_DELAY]["milliseconds"]

#         delta = timedelta(
#             hours=hours, minutes=minutes, seconds=seconds, milliseconds=milliseconds
#         )

#         for entity in parents:
#             entity.delay = delta

#         next_parents = parents

#     else:
#         config[CONF_STEP] = config[CONF_STEP] + 1
#         action_id = config[CONF_ROUTINE_ID] + str(config[CONF_STEP])

#         entities[action_id] = ActionEntity(
#             hass=hass,
#             action=script,
#             action_id=action_id,
#             action_state=None,
#             lock_state=None,
#             routine_id=config[CONF_ROUTINE_ID],
#             logger=_LOGGER,
#         )

#         for entity in parents:
#             entities[action_id].parents.append(entity)

#         for entity in parents:
#             entity.children.append(entities[action_id])

#         next_parents.append(entities[action_id])

#     return next_parents

# class RoutineEntity:
#     """A class that describes routine entities for Rascal Scheduler."""

#     def __init__(
#         self,
#         name: str | None,
#         routine_id: str | None,
#         actions: dict[str, ActionEntity],
#         timeout: float,
#         logger: logging.Logger | None = None,
#         log_exceptions: bool = True,
#     ) -> None:
#         """Initialize a routine entity."""
#         self._name = name
#         self._routine_id = routine_id
#         self.actions = actions
#         self._start_time: float | None = None
#         self._last_trigger_time: float | None = None
#         self._timeout = timeout
#         self._set_logger(logger)
#         self._log_exceptions = log_exceptions

#     @property
#     def name(self)->str:
#         """Get name."""
#         return self._name

#     @property
#     def routine_id(self)->str:
#         """Get routine id."""
#         return self._routine_id

#     @property
#     def start_time(self) -> float | None:
#         """Get the start time of the routine entity."""
#         return self._start_time

#     @property
#     def last_trigger_time(self) -> float | None:
#         """Get the last trigger time or the routine entity."""
#         return self._last_trigger_time

#     @property
#     def timeout(self) -> float:
#         """Return the timeout of the routine entity."""
#         return self._timeout

#     def set_variables(self, var: dict[str, Any]) -> None:
#         """Set variables to all the action entities."""
#         for entity in self.actions.values():
#             entity.variables = var

#     def set_context(self, ctx: Context | None) -> None:
#         """Set context to all the action entities."""
#         for entity in self.actions.values():
#             entity.context = ctx

#     def _set_logger(self, logger: logging.Logger | None = None) -> None:
#         """Set logger."""
#         if logger:
#             self._logger = logger
#         else:
#             self._logger = logging.getLogger(f"{__name__}.{slugify(self.name)}")

#     def duplicate(self) -> RoutineEntity:
#         """Duplicate the routine entity."""

#         routine_entity = {}

#         for action_id, entity in self.actions.items():
#             if action_id is not None:
#                 routine_entity[action_id] = ActionEntity(
#                     hass=entity.hass,
#                     action=entity.action,
#                     action_id=entity.action_id,
#                     action_state=RASC_SCHEDULED,
#                     lock_state=LOCK_STATE_SCHEDULED,
#                     routine_id=entity.routine_id,
#                     delay=entity.delay,
#                     group=entity.group,
#                     logger=entity.get_logger(),
#                 )

#         for action_id, entity in self.actions.items():
#             if action_id is not None:
#                 for parent in entity.parents:
#                     if parent.action_id is not None:
#                         routine_entity[action_id].parents.append(
#                             routine_entity[parent.action_id]
#                         )

#                 for child in entity.children:
#                     if child.action_id is not None:
#                         routine_entity[action_id].children.append(
#                             routine_entity[child.action_id]
#                         )
#                     else:
#                         routine_entity[action_id].children.append(
#                             routine_entity["end_virtual_node"]
#                         )

#         if self._last_trigger_time is None:
#             self._start_time = time.time()
#             self._last_trigger_time = self._start_time
#         else:
#             self._last_trigger_time = self._start_time
#             self._start_time = time.time()

#         return RoutineEntity(
#             self.name, self.routine_id, routine_entity, self._timeout, self._logger
#         )

#     def output(self) -> None:
#         """Print the routine information."""
#         actions = []
#         for _, entity in self.actions.items():
#             parents = []
#             children = []

#             for parent in entity.parents:
#                 parents.append(parent.action_id)

#             for child in entity.children:
#                 children.append(child.action_id)

#             entity_json = {
#                 "action_id": entity.action_id,
#                 "action": entity.action,
#                 "action state": entity.action_state,
#                 "lock state": entity.lock_state,
#                 "parents": parents,
#                 "children": children,
#                 "group": entity.group,
#                 "delay": str(entity.delay),
#             }

#             actions.append(entity_json)

#         out = {"routine_id": self.routine_id, "actions": actions}

#         print(json.dumps(out, indent=2))  # noqa: T201


# class ActionEntity:
#     """Initialize a routine entity."""

#     def __init__(
#         self,
#         hass: HomeAssistant,
#         action: dict[str, Any],
#         action_id: str | None,
#         action_state: str | None,
#         lock_state: str | None,
#         routine_id: str | None,
#         delay: timedelta | None = None,
#         group: bool = False,
#         logger: logging.Logger | None = None,
#     ) -> None:
#         """Initialize a routine entity."""
#         self.hass = hass
#         self.action = action
#         self._action_id = action_id
#         self._action_state = action_state
#         self._lock_state = lock_state
#         self._routine_id = routine_id
#         self.parents: list[ActionEntity] = []
#         self.children: list[ActionEntity] = []
#         self.delay = delay
#         self.group = group
#         self.variables: dict[str, Any]
#         self.context: Context | None
#         self._log_exceptions = False
#         self._set_logger(logger)
#         self._stop = asyncio.Event()

#     @property
#     def action_id(self)->str | None:
#         """Get action id."""
#         return self._action_id

#     @property
#     def routine_id(self)->str | None:
#         """Get routine id."""
#         return self._routine_id

#     @property
#     def action_state(self)->str | None:
#         """Get action state"""
#         return self._action_state

#     @action_state.setter
#     def action_state(self, state:str)->None:
#         """Set action state."""
#         self._action_state = state

#     @property
#     def lock_state(self)->str | None:
#         """Get lock state."""
#         return self._lock_state

#     @lock_state.setter
#     def lock_state(self, state: str) -> None:
#         """Set lock state."""
#         self._lock_state = state

#     def get_logger(self) -> logging.Logger | None:
#         """Get logger."""
#         return self._logger

#     def _set_logger(self, logger: logging.Logger | None = None) -> None:
#         """Set logger."""
#         self._logger = logger

#     def _step_log(self, default_message: Any, timeout: Any = None) -> None:
#         """Step log."""
#         _timeout = (
#             "" if timeout is None else f" (timeout: {timedelta(seconds=timeout)})"
#         )
#         self._log(
#             "Executing step %s%s", default_message, _timeout
#         )  # pylint: disable=protected-access

#     def _log(
#         self, msg: str, *args: Any, level: int = logging.INFO, **kwargs: Any
#     ) -> None:
#         """Log."""
#         msg = f"%s: {msg}"
#         args = (str(self.action_id), *args)

#         if self._logger is not None:
#             if level == _LOG_EXCEPTION:
#                 self._logger.exception(msg, *args, **kwargs)
#             else:
#                 self._logger.log(level, msg, *args, **kwargs)

#     async def attach_triggered(self, log_exceptions: bool) -> None:
#         """Trigger the function."""
#         action = cv.determine_script_action(self.action)
#         print("action:", self.action)
#         self.action['entity_id'] = async_get_entity_id_from_number(self.hass, self.action['entity_id'])
#         continue_on_error = self.action.get(CONF_CONTINUE_ON_ERROR, False)

#         try:
#             handler = f"_async_{action}_step"
#             await getattr(self, handler)()

#         except Exception as ex:  # pylint: disable=broad-except
#             self._handle_exception(
#                 ex, continue_on_error, self._log_exceptions or log_exceptions
#             )

#     async def _async_device_step(self) -> None:
#         """Execute device automation."""
#         await device_action.async_call_action_from_config(
#             self.hass, self.action, self.variables, self.context
#         )

#     async def async_delay_step(self) -> None:
#         """Handle delay."""
#         await self._async_delay_step()

#     async def _async_delay_step(self) -> None:
#         """Handle delay."""
#         if self.delay is not None:
#             delay = self.delay
#             self._step_log(f"delay {delay}")

#             try:
#                 async with asyncio.timeout(delay.total_seconds()):
#                     await self._stop.wait()
#             except asyncio.TimeoutError:
#                 self._step_log("delay completed")

#     async def _async_call_service_step(self) -> None:
#         """Call the service specified in the action."""
#         self._step_log("call service")

#         params = service.async_prepare_call_from_config(
#             self.hass, self.action, self.variables
#         )

#         # Validate response data parameters. This check ignores services that do
#         # not exist which will raise an appropriate error in the service call below.
#         response_variable = self.action.get(CONF_RESPONSE_VARIABLE)

#         return_response = response_variable is not None

#         response_data = await self._async_run_long_action(
#             self.hass.async_create_task(
#                 self.hass.services.async_call(
#                     **params,
#                     blocking=True,
#                     context=self.context,
#                     return_response=return_response,
#                 )
#             ),
#         )
#         if response_variable:
#             self.variables[response_variable] = response_data

#     async def _async_run_long_action(self, long_task: asyncio.Task[_T]) -> _T | None:
#         """Run a long task while monitoring for stop request."""

#         async def async_cancel_long_task() -> None:
#             # Stop long task and wait for it to finish.
#             long_task.cancel()
#             with suppress(Exception):
#                 await long_task

#         # Wait for long task while monitoring for a stop request.
#         stop_task = self.hass.async_create_task(self._stop.wait())
#         try:
#             await asyncio.wait(
#                 {long_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
#             )
#         # If our task is cancelled, then cancel long task, too. Note that if long task
#         # is cancelled otherwise the CancelledError exception will not be raised to
#         # here due to the call to asyncio.wait(). Rather we'll check for that below.
#         except asyncio.CancelledError:
#             await async_cancel_long_task()
#             raise
#         finally:
#             stop_task.cancel()

#         if long_task.cancelled():
#             raise asyncio.CancelledError
#         if long_task.done():
#             # Propagate any exceptions that occurred.
#             return long_task.result()
#         # Stopped before long task completed, so cancel it.
#         await async_cancel_long_task()
#         return None

#     def _handle_exception(
#         self, exception: Exception, continue_on_error: bool, log_exceptions: bool
#     ) -> None:
#         if not isinstance(exception, _HaltScript) and log_exceptions:
#             self._log_exception(exception)

#         if not continue_on_error:
#             raise exception

#         # An explicit request to stop the script has been raised.
#         if isinstance(exception, _StopScript):
#             raise exception

#         # These are incorrect scripts, and not runtime errors that need to
#         # be handled and thus cannot be stopped by `continue_on_error`.
#         if isinstance(
#             exception,
#             (
#                 vol.Invalid,
#                 exceptions.TemplateError,
#                 exceptions.ServiceNotFound,
#                 exceptions.InvalidEntityFormatError,
#                 exceptions.NoEntitySpecifiedError,
#                 exceptions.ConditionError,
#             ),
#         ):
#             raise exception

#         # Only Home Assistant errors can be ignored.
#         if not isinstance(exception, exceptions.HomeAssistantError):
#             raise exception

#     def _log_exception(self, exception: Exception) -> None:
#         """Log exception."""
#         action_type = cv.determine_script_action(self.action)

#         error = str(exception)

#         if isinstance(exception, vol.Invalid):
#             error_desc = "Invalid data"

#         elif isinstance(exception, exceptions.TemplateError):
#             error_desc = "Error rendering template"

#         elif isinstance(exception, exceptions.Unauthorized):
#             error_desc = "Unauthorized"

#         elif isinstance(exception, exceptions.ServiceNotFound):
#             error_desc = "Service not found"

#         elif isinstance(exception, exceptions.HomeAssistantError):
#             error_desc = "Error"

#         else:
#             error_desc = "Unexpected error"

#         _LOGGER.warning(
#             "Error executing script. %s for %s at action_id %s: %s",
#             error_desc,
#             action_type,
#             self.action_id,
#             error,
#         )


# class OrderedQueueEntity(OrderedDict[_KT, _VT]):
#     """Representation of a queue for a scheduler with order maintenance."""

#     __slots__ = ("_queue",)

#     _queue: OrderedDict[_KT, _VT]

#     def __init__(self, queue: Any = None) -> None:
#         """Initialize a queue entity."""
#         self._queue = OrderedDict() if queue is None else OrderedDict(queue)

#     def __getitem__(self, key: _KT) -> _VT:
#         """Get item."""
#         return self._queue[key]

#     def __setitem__(self, key: _KT, value: _VT) -> None:
#         """Set item."""
#         self._queue[key] = value

#     def __delitem__(self, key: _KT) -> None:
#         """Delete item."""
#         del self._queue[key]

#     def __iter__(self) -> Iterator[_KT]:
#         """Iterate items."""
#         return iter(self._queue)

#     def __len__(self) -> int:
#         """Get the size of the queue."""
#         return len(self._queue)


# class QueueEntity(MutableSequence[_VT]):
#     """Representation of an queue for rascal scheduler."""

#     __slots__ = ("_queue_entities",)

#     _queue_entities: list[_VT]

#     def __init__(self, queue_entities: Any) -> None:
#         """Initialize a queue entity."""
#         self._queue_entities = [] if queue_entities is None else queue_entities

#     def __getitem__(self, __key: Any) -> Any:
#         """Get item."""
#         return self._queue_entities[__key]

#     def __delitem__(self, __key: Any) -> Any:
#         """Delete item."""
#         self._queue_entities.pop(__key)

#     def __len__(self) -> int:
#         """Get the size of the queue."""
#         return len(self._queue_entities)

#     def __setitem__(self, __key: Any, __value: Any) -> None:
#         """Set item."""
#         self._queue_entities[__key] = __value

#     def insert(self, __key: Any, __value: Any) -> None:
#         """Insert key value pair."""
#         self._queue_entities.insert(__key, __value)

#     def empty(self) -> bool:
#         """Return empty."""
#         return len(self._queue_entities) == 0

#     def append(self, __value: Any) -> None:
#         """Append new value."""
#         self._queue_entities.append(__value)


# class _HaltScript(Exception):
#     """Throw if script needs to stop executing."""


# class _StopScript(_HaltScript):
#     """Throw if script needs to stop."""

#     def __init__(self, message: str, response: Any) -> None:
#         """Initialize a halt exception."""
#         super().__init__(message)
#         self.response = response
