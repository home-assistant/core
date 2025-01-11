"""Helpers to execute scripts."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from contextvars import ContextVar
from copy import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
import itertools
import logging
from types import MappingProxyType
from typing import Any, Literal, TypedDict, cast, overload

import async_interrupt
from propcache import cached_property
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components import scene
from homeassistant.components.device_automation import action as device_action
from homeassistant.components.logger import LOGSEVERITY
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ALIAS,
    CONF_CHOOSE,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_CONTINUE_ON_ERROR,
    CONF_CONTINUE_ON_TIMEOUT,
    CONF_COUNT,
    CONF_DEFAULT,
    CONF_DELAY,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ELSE,
    CONF_ENABLED,
    CONF_ERROR,
    CONF_EVENT,
    CONF_EVENT_DATA,
    CONF_EVENT_DATA_TEMPLATE,
    CONF_FOR_EACH,
    CONF_IF,
    CONF_MODE,
    CONF_PARALLEL,
    CONF_REPEAT,
    CONF_RESPONSE_VARIABLE,
    CONF_SCENE,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_SERVICE_DATA,
    CONF_SERVICE_DATA_TEMPLATE,
    CONF_SET_CONVERSATION_RESPONSE,
    CONF_STOP,
    CONF_TARGET,
    CONF_THEN,
    CONF_TIMEOUT,
    CONF_UNTIL,
    CONF_VARIABLES,
    CONF_WAIT_FOR_TRIGGER,
    CONF_WAIT_TEMPLATE,
    CONF_WHILE,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_ON,
)
from homeassistant.core import (
    Context,
    Event,
    HassJob,
    HomeAssistant,
    ServiceResponse,
    State,
    SupportsResponse,
    callback,
)
from homeassistant.util import slugify
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.dt import utcnow
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.signal_type import SignalType, SignalTypeFormat

from . import condition, config_validation as cv, service, template
from .condition import ConditionCheckerType, trace_condition_function
from .dispatcher import async_dispatcher_connect, async_dispatcher_send_internal
from .event import async_call_later, async_track_template
from .script_variables import ScriptVariables
from .template import Template
from .trace import (
    TraceElement,
    async_trace_path,
    script_execution_set,
    trace_append_element,
    trace_id_get,
    trace_path,
    trace_path_get,
    trace_path_stack_cv,
    trace_set_result,
    trace_stack_cv,
    trace_stack_pop,
    trace_stack_push,
    trace_stack_top,
    trace_update_result,
)
from .trigger import async_initialize_triggers, async_validate_trigger_config
from .typing import UNDEFINED, ConfigType, TemplateVarsType, UndefinedType

SCRIPT_MODE_PARALLEL = "parallel"
SCRIPT_MODE_QUEUED = "queued"
SCRIPT_MODE_RESTART = "restart"
SCRIPT_MODE_SINGLE = "single"
SCRIPT_MODE_CHOICES = [
    SCRIPT_MODE_PARALLEL,
    SCRIPT_MODE_QUEUED,
    SCRIPT_MODE_RESTART,
    SCRIPT_MODE_SINGLE,
]
DEFAULT_SCRIPT_MODE = SCRIPT_MODE_SINGLE

CONF_MAX = "max"
DEFAULT_MAX = 10

CONF_MAX_EXCEEDED = "max_exceeded"
_MAX_EXCEEDED_CHOICES = [*LOGSEVERITY, "SILENT"]
DEFAULT_MAX_EXCEEDED = "WARNING"

ATTR_CUR = "current"
ATTR_MAX = "max"

DATA_SCRIPTS: HassKey[list[ScriptData]] = HassKey("helpers.script")
DATA_SCRIPT_BREAKPOINTS: HassKey[dict[str, dict[str, set[str]]]] = HassKey(
    "helpers.script_breakpoints"
)
DATA_NEW_SCRIPT_RUNS_NOT_ALLOWED: HassKey[None] = HassKey("helpers.script_not_allowed")
RUN_ID_ANY = "*"
NODE_ANY = "*"

_LOGGER = logging.getLogger(__name__)

_LOG_EXCEPTION = logging.ERROR + 1
_TIMEOUT_MSG = "Timeout reached, abort script."

_SHUTDOWN_MAX_WAIT = 60


ACTION_TRACE_NODE_MAX_LEN = 20  # Max length of a trace node for repeated actions

SCRIPT_BREAKPOINT_HIT = SignalType[str, str, str]("script_breakpoint_hit")
SCRIPT_DEBUG_CONTINUE_STOP: SignalTypeFormat[Literal["continue", "stop"]] = (
    SignalTypeFormat("script_debug_continue_stop_{}_{}")
)
SCRIPT_DEBUG_CONTINUE_ALL = "script_debug_continue_all"

script_stack_cv: ContextVar[list[str] | None] = ContextVar("script_stack", default=None)


class ScriptData(TypedDict):
    """Store data related to script instance."""

    instance: Script
    started_before_shutdown: bool


class ScriptStoppedError(Exception):
    """Error to indicate that the script has been stopped."""


def _set_result_unless_done(future: asyncio.Future[None]) -> None:
    """Set result of future unless it is done."""
    if not future.done():
        future.set_result(None)


def action_trace_append(variables: dict[str, Any], path: str) -> TraceElement:
    """Append a TraceElement to trace[path]."""
    trace_element = TraceElement(variables, path)
    trace_append_element(trace_element, ACTION_TRACE_NODE_MAX_LEN)
    return trace_element


@asynccontextmanager
async def trace_action(
    hass: HomeAssistant,
    script_run: _ScriptRun,
    stop: asyncio.Future[None],
    variables: dict[str, Any],
) -> AsyncGenerator[TraceElement]:
    """Trace action execution."""
    path = trace_path_get()
    trace_element = action_trace_append(variables, path)
    trace_stack_push(trace_stack_cv, trace_element)

    trace_id = trace_id_get()
    if trace_id:
        key = trace_id[0]
        run_id = trace_id[1]
        breakpoints = hass.data[DATA_SCRIPT_BREAKPOINTS]
        if key in breakpoints and (
            (
                run_id in breakpoints[key]
                and (
                    path in breakpoints[key][run_id]
                    or NODE_ANY in breakpoints[key][run_id]
                )
            )
            or (
                RUN_ID_ANY in breakpoints[key]
                and (
                    path in breakpoints[key][RUN_ID_ANY]
                    or NODE_ANY in breakpoints[key][RUN_ID_ANY]
                )
            )
        ):
            async_dispatcher_send_internal(
                hass, SCRIPT_BREAKPOINT_HIT, key, run_id, path
            )

            done = hass.loop.create_future()

            @callback
            def async_continue_stop(
                command: Literal["continue", "stop"] | None = None,
            ) -> None:
                if command == "stop":
                    _set_result_unless_done(stop)
                _set_result_unless_done(done)

            signal = SCRIPT_DEBUG_CONTINUE_STOP.format(key, run_id)
            remove_signal1 = async_dispatcher_connect(hass, signal, async_continue_stop)
            remove_signal2 = async_dispatcher_connect(
                hass, SCRIPT_DEBUG_CONTINUE_ALL, async_continue_stop
            )

            await asyncio.wait([stop, done], return_when=asyncio.FIRST_COMPLETED)
            remove_signal1()
            remove_signal2()

    try:
        yield trace_element
    except _AbortScript as ex:
        trace_element.set_error(ex.__cause__ or ex)
        raise
    except _ConditionFail:
        # Clear errors which may have been set when evaluating the condition
        trace_element.set_error(None)
        raise
    except _StopScript:
        raise
    except Exception as ex:
        trace_element.set_error(ex)
        raise
    finally:
        trace_stack_pop(trace_stack_cv)


def make_script_schema(
    schema: Mapping[Any, Any], default_script_mode: str, extra: int = vol.PREVENT_EXTRA
) -> vol.Schema:
    """Make a schema for a component that uses the script helper."""
    return vol.Schema(
        {
            **schema,
            vol.Optional(CONF_MODE, default=default_script_mode): vol.In(
                SCRIPT_MODE_CHOICES
            ),
            vol.Optional(CONF_MAX, default=DEFAULT_MAX): vol.All(
                vol.Coerce(int), vol.Range(min=2)
            ),
            vol.Optional(CONF_MAX_EXCEEDED, default=DEFAULT_MAX_EXCEEDED): vol.All(
                vol.Upper, vol.In(_MAX_EXCEEDED_CHOICES)
            ),
        },
        extra=extra,
    )


STATIC_VALIDATION_ACTION_TYPES = (
    cv.SCRIPT_ACTION_ACTIVATE_SCENE,
    cv.SCRIPT_ACTION_CALL_SERVICE,
    cv.SCRIPT_ACTION_DELAY,
    cv.SCRIPT_ACTION_FIRE_EVENT,
    cv.SCRIPT_ACTION_SET_CONVERSATION_RESPONSE,
    cv.SCRIPT_ACTION_STOP,
    cv.SCRIPT_ACTION_VARIABLES,
    cv.SCRIPT_ACTION_WAIT_TEMPLATE,
)

REPEAT_WARN_ITERATIONS = 5000
REPEAT_TERMINATE_ITERATIONS = 10000


async def async_validate_actions_config(
    hass: HomeAssistant, actions: list[ConfigType]
) -> list[ConfigType]:
    """Validate a list of actions."""
    # No gather here because async_validate_action_config is unlikely
    # to suspend and the overhead of creating many tasks is not worth it
    return [await async_validate_action_config(hass, action) for action in actions]


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    action_type = cv.determine_script_action(config)

    if action_type in STATIC_VALIDATION_ACTION_TYPES:
        pass

    elif action_type == cv.SCRIPT_ACTION_DEVICE_AUTOMATION:
        config = await device_action.async_validate_action_config(hass, config)

    elif action_type == cv.SCRIPT_ACTION_CHECK_CONDITION:
        config = await condition.async_validate_condition_config(hass, config)

    elif action_type == cv.SCRIPT_ACTION_WAIT_FOR_TRIGGER:
        config[CONF_WAIT_FOR_TRIGGER] = await async_validate_trigger_config(
            hass, config[CONF_WAIT_FOR_TRIGGER]
        )

    elif action_type == cv.SCRIPT_ACTION_REPEAT:
        if CONF_UNTIL in config[CONF_REPEAT]:
            conditions = await condition.async_validate_conditions_config(
                hass, config[CONF_REPEAT][CONF_UNTIL]
            )
            config[CONF_REPEAT][CONF_UNTIL] = conditions
        if CONF_WHILE in config[CONF_REPEAT]:
            conditions = await condition.async_validate_conditions_config(
                hass, config[CONF_REPEAT][CONF_WHILE]
            )
            config[CONF_REPEAT][CONF_WHILE] = conditions
        config[CONF_REPEAT][CONF_SEQUENCE] = await async_validate_actions_config(
            hass, config[CONF_REPEAT][CONF_SEQUENCE]
        )

    elif action_type == cv.SCRIPT_ACTION_CHOOSE:
        if CONF_DEFAULT in config:
            config[CONF_DEFAULT] = await async_validate_actions_config(
                hass, config[CONF_DEFAULT]
            )

        for choose_conf in config[CONF_CHOOSE]:
            conditions = await condition.async_validate_conditions_config(
                hass, choose_conf[CONF_CONDITIONS]
            )
            choose_conf[CONF_CONDITIONS] = conditions
            choose_conf[CONF_SEQUENCE] = await async_validate_actions_config(
                hass, choose_conf[CONF_SEQUENCE]
            )

    elif action_type == cv.SCRIPT_ACTION_IF:
        config[CONF_IF] = await condition.async_validate_conditions_config(
            hass, config[CONF_IF]
        )
        config[CONF_THEN] = await async_validate_actions_config(hass, config[CONF_THEN])
        if CONF_ELSE in config:
            config[CONF_ELSE] = await async_validate_actions_config(
                hass, config[CONF_ELSE]
            )

    elif action_type == cv.SCRIPT_ACTION_PARALLEL:
        for parallel_conf in config[CONF_PARALLEL]:
            parallel_conf[CONF_SEQUENCE] = await async_validate_actions_config(
                hass, parallel_conf[CONF_SEQUENCE]
            )

    elif action_type == cv.SCRIPT_ACTION_SEQUENCE:
        config[CONF_SEQUENCE] = await async_validate_actions_config(
            hass, config[CONF_SEQUENCE]
        )

    else:
        raise ValueError(f"No validation for {action_type}")

    return config


class _HaltScript(Exception):
    """Throw if script needs to stop executing."""


class _AbortScript(_HaltScript):
    """Throw if script needs to abort because of an unexpected error."""


class _ConditionFail(_HaltScript):
    """Throw if script needs to stop because a condition evaluated to False."""


class _StopScript(_HaltScript):
    """Throw if script needs to stop."""

    def __init__(self, message: str, response: Any) -> None:
        """Initialize a halt exception."""
        super().__init__(message)
        self.response = response


class _ScriptRun:
    """Manage Script sequence run."""

    _action: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        script: Script,
        variables: dict[str, Any],
        context: Context | None,
        log_exceptions: bool,
    ) -> None:
        self._hass = hass
        self._script = script
        self._variables = variables
        self._context = context
        self._log_exceptions = log_exceptions
        self._step = -1
        self._started = False
        self._stop = hass.loop.create_future()
        self._stopped = asyncio.Event()
        self._conversation_response: str | None | UndefinedType = UNDEFINED

    def _changed(self) -> None:
        if not self._stop.done():
            self._script._changed()  # noqa: SLF001

    async def _async_get_condition(self, config: ConfigType) -> ConditionCheckerType:
        return await self._script._async_get_condition(config)  # noqa: SLF001

    def _log(
        self, msg: str, *args: Any, level: int = logging.INFO, **kwargs: Any
    ) -> None:
        self._script._log(msg, *args, level=level, **kwargs)  # noqa: SLF001

    def _step_log(self, default_message: str, timeout: float | None = None) -> None:
        self._script.last_action = self._action.get(CONF_ALIAS, default_message)
        _timeout = (
            "" if timeout is None else f" (timeout: {timedelta(seconds=timeout)})"
        )
        self._log("Executing step %s%s", self._script.last_action, _timeout)

    async def async_run(self) -> ScriptRunResult | None:
        """Run script."""
        self._started = True
        # Push the script to the script execution stack
        if (script_stack := script_stack_cv.get()) is None:
            script_stack = []
            script_stack_cv.set(script_stack)
        script_stack.append(self._script.unique_id)
        response = None

        try:
            self._log("Running %s", self._script.running_description)
            for self._step, self._action in enumerate(self._script.sequence):
                if self._stop.done():
                    script_execution_set("cancelled")
                    break
                await self._async_step(log_exceptions=False)
            else:
                script_execution_set("finished")
        except _AbortScript:
            script_execution_set("aborted")
            # Let the _AbortScript bubble up if this is a sub-script
            if not self._script.top_level:
                raise
        except _ConditionFail:
            script_execution_set("aborted")
        except _StopScript as err:
            script_execution_set("finished", err.response)

            # Let the _StopScript bubble up if this is a sub-script
            if not self._script.top_level:
                raise

            response = err.response

        except Exception:
            script_execution_set("error")
            raise
        finally:
            # Pop the script from the script execution stack
            script_stack.pop()
            self._finish()

        return ScriptRunResult(self._conversation_response, response, self._variables)

    async def _async_step(self, log_exceptions: bool) -> None:
        continue_on_error = self._action.get(CONF_CONTINUE_ON_ERROR, False)

        with trace_path(str(self._step)):
            async with trace_action(
                self._hass, self, self._stop, self._variables
            ) as trace_element:
                if self._stop.done():
                    return

                action = cv.determine_script_action(self._action)

                if CONF_ENABLED in self._action:
                    enabled = self._action[CONF_ENABLED]
                    if isinstance(enabled, Template):
                        try:
                            enabled = enabled.async_render(limited=True)
                        except exceptions.TemplateError as ex:
                            self._handle_exception(
                                ex,
                                continue_on_error,
                                self._log_exceptions or log_exceptions,
                            )
                    if not enabled:
                        self._log(
                            "Skipped disabled step %s",
                            self._action.get(CONF_ALIAS, action),
                        )
                        trace_set_result(enabled=False)
                        return

                handler = f"_async_{action}_step"
                try:
                    await getattr(self, handler)()
                except Exception as ex:  # noqa: BLE001
                    self._handle_exception(
                        ex, continue_on_error, self._log_exceptions or log_exceptions
                    )
                finally:
                    trace_element.update_variables(self._variables)

    def _finish(self) -> None:
        self._script._runs.remove(self)  # noqa: SLF001
        if not self._script.is_running:
            self._script.last_action = None
        self._changed()
        self._stopped.set()

    async def async_stop(self) -> None:
        """Stop script run."""
        _set_result_unless_done(self._stop)
        # If the script was never started
        # the stopped event will never be
        # set because the script will never
        # start running
        if self._started:
            await self._stopped.wait()

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
        action_type = cv.determine_script_action(self._action)

        error = str(exception)
        level = logging.ERROR

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
            level = _LOG_EXCEPTION

        self._log(
            "Error executing script. %s for %s at pos %s: %s",
            error_desc,
            action_type,
            self._step + 1,
            error,
            level=level,
        )

    def _get_pos_time_period_template(self, key: str) -> timedelta:
        try:
            return cv.positive_time_period(  # type: ignore[no-any-return]
                template.render_complex(self._action[key], self._variables)
            )
        except (exceptions.TemplateError, vol.Invalid) as ex:
            self._log(
                "Error rendering %s %s template: %s",
                self._script.name,
                key,
                ex,
                level=logging.ERROR,
            )
            raise _AbortScript from ex

    async def _async_delay_step(self) -> None:
        """Handle delay."""
        delay_delta = self._get_pos_time_period_template(CONF_DELAY)

        self._step_log(f"delay {delay_delta}")

        delay = delay_delta.total_seconds()
        self._changed()
        if not delay:
            # Handle an empty delay
            trace_set_result(delay=delay, done=True)
            return

        trace_set_result(delay=delay, done=False)
        futures, timeout_handle, timeout_future = self._async_futures_with_timeout(
            delay
        )

        try:
            await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED)
        finally:
            if timeout_future.done():
                trace_set_result(delay=delay, done=True)
            else:
                timeout_handle.cancel()

    def _get_timeout_seconds_from_action(self) -> float | None:
        """Get the timeout from the action."""
        if CONF_TIMEOUT in self._action:
            return self._get_pos_time_period_template(CONF_TIMEOUT).total_seconds()
        return None

    async def _async_wait_template_step(self) -> None:
        """Handle a wait template."""
        timeout = self._get_timeout_seconds_from_action()
        self._step_log("wait template", timeout)

        self._variables["wait"] = {"remaining": timeout, "completed": False}
        trace_set_result(wait=self._variables["wait"])

        wait_template = self._action[CONF_WAIT_TEMPLATE]

        # check if condition already okay
        if condition.async_template(self._hass, wait_template, self._variables, False):
            self._variables["wait"]["completed"] = True
            self._changed()
            return

        if timeout == 0:
            self._changed()
            self._async_handle_timeout()
            return

        futures, timeout_handle, timeout_future = self._async_futures_with_timeout(
            timeout
        )
        done = self._hass.loop.create_future()
        futures.append(done)

        @callback
        def async_script_wait(
            entity_id: str, from_s: State | None, to_s: State | None
        ) -> None:
            """Handle script after template condition is true."""
            self._async_set_remaining_time_var(timeout_handle)
            self._variables["wait"]["completed"] = True
            _set_result_unless_done(done)

        unsub = async_track_template(
            self._hass, wait_template, async_script_wait, self._variables
        )
        self._changed()
        await self._async_wait_with_optional_timeout(
            futures, timeout_handle, timeout_future, unsub
        )

    def _async_set_remaining_time_var(
        self, timeout_handle: asyncio.TimerHandle | None
    ) -> None:
        """Set the remaining time variable for a wait step."""
        wait_var = self._variables["wait"]
        if timeout_handle:
            wait_var["remaining"] = timeout_handle.when() - self._hass.loop.time()
        else:
            wait_var["remaining"] = None

    async def _async_run_long_action[_T](
        self, long_task: asyncio.Task[_T]
    ) -> _T | None:
        """Run a long task while monitoring for stop request."""
        try:
            async with async_interrupt.interrupt(self._stop, ScriptStoppedError, None):
                # if stop is set, interrupt will cancel inside the context
                # manager which will cancel long_task, and raise
                # ScriptStoppedError outside the context manager
                return await long_task
        except ScriptStoppedError as ex:
            raise asyncio.CancelledError from ex

    async def _async_call_service_step(self) -> None:
        """Call the service specified in the action."""
        self._step_log("call service")

        params = service.async_prepare_call_from_config(
            self._hass, self._action, self._variables
        )

        # Validate response data parameters. This check ignores services that do
        # not exist which will raise an appropriate error in the service call below.
        response_variable = self._action.get(CONF_RESPONSE_VARIABLE)
        return_response = response_variable is not None
        if self._hass.services.has_service(params[CONF_DOMAIN], params[CONF_SERVICE]):
            supports_response = self._hass.services.supports_response(
                params[CONF_DOMAIN], params[CONF_SERVICE]
            )
            if supports_response == SupportsResponse.ONLY and not return_response:
                raise vol.Invalid(
                    f"Script requires '{CONF_RESPONSE_VARIABLE}' for response data "
                    f"for service call {params[CONF_DOMAIN]}.{params[CONF_SERVICE]}"
                )
            if supports_response == SupportsResponse.NONE and return_response:
                raise vol.Invalid(
                    f"Script does not support '{CONF_RESPONSE_VARIABLE}' for service "
                    f"'{CONF_RESPONSE_VARIABLE}' which does not support response data."
                )

        running_script = (
            params[CONF_DOMAIN] == "automation"
            and params[CONF_SERVICE] == "trigger"
            or params[CONF_DOMAIN] in ("python_script", "script")
        )
        trace_set_result(params=params, running_script=running_script)
        response_data = await self._async_run_long_action(
            self._hass.async_create_task_internal(
                self._hass.services.async_call(
                    **params,
                    blocking=True,
                    context=self._context,
                    return_response=return_response,
                ),
                eager_start=True,
            )
        )
        if response_variable:
            self._variables[response_variable] = response_data

    async def _async_device_step(self) -> None:
        """Perform the device automation specified in the action."""
        self._step_log("device automation")
        await device_action.async_call_action_from_config(
            self._hass, self._action, self._variables, self._context
        )

    async def _async_scene_step(self) -> None:
        """Activate the scene specified in the action."""
        self._step_log("activate scene")
        trace_set_result(scene=self._action[CONF_SCENE])
        await self._hass.services.async_call(
            scene.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self._action[CONF_SCENE]},
            blocking=True,
            context=self._context,
        )

    async def _async_event_step(self) -> None:
        """Fire an event."""
        self._step_log(self._action.get(CONF_ALIAS, self._action[CONF_EVENT]))
        event_data = {}
        for conf in (CONF_EVENT_DATA, CONF_EVENT_DATA_TEMPLATE):
            if conf not in self._action:
                continue

            try:
                event_data.update(
                    template.render_complex(self._action[conf], self._variables)
                )
            except exceptions.TemplateError as ex:
                self._log(
                    "Error rendering event data template: %s", ex, level=logging.ERROR
                )

        trace_set_result(event=self._action[CONF_EVENT], event_data=event_data)
        self._hass.bus.async_fire_internal(
            self._action[CONF_EVENT], event_data, context=self._context
        )

    async def _async_condition_step(self) -> None:
        """Test if condition is matching."""
        self._script.last_action = self._action.get(
            CONF_ALIAS, self._action[CONF_CONDITION]
        )
        cond = await self._async_get_condition(self._action)
        try:
            trace_element = trace_stack_top(trace_stack_cv)
            if trace_element:
                trace_element.reuse_by_child = True
            check = cond(self._hass, self._variables)
        except exceptions.ConditionError as ex:
            _LOGGER.warning("Error in 'condition' evaluation:\n%s", ex)
            check = False

        self._log("Test condition %s: %s", self._script.last_action, check)
        trace_update_result(result=check)
        if not check:
            raise _ConditionFail

    def _test_conditions(
        self,
        conditions: list[ConditionCheckerType],
        name: str,
        condition_path: str | None = None,
    ) -> bool | None:
        if condition_path is None:
            condition_path = name

        @trace_condition_function
        def traced_test_conditions(
            hass: HomeAssistant, variables: TemplateVarsType
        ) -> bool | None:
            try:
                with trace_path(condition_path):
                    for idx, cond in enumerate(conditions):
                        with trace_path(str(idx)):
                            if cond(hass, variables) is False:
                                return False
            except exceptions.ConditionError as ex:
                _LOGGER.warning("Error in '%s[%s]' evaluation: %s", name, idx, ex)
                return None

            return True

        return traced_test_conditions(self._hass, self._variables)

    @async_trace_path("repeat")
    async def _async_repeat_step(self) -> None:  # noqa: C901
        """Repeat a sequence."""
        description = self._action.get(CONF_ALIAS, "sequence")
        repeat = self._action[CONF_REPEAT]

        saved_repeat_vars = self._variables.get("repeat")

        def set_repeat_var(
            iteration: int, count: int | None = None, item: Any = None
        ) -> None:
            repeat_vars = {"first": iteration == 1, "index": iteration}
            if count:
                repeat_vars["last"] = iteration == count
            if item is not None:
                repeat_vars["item"] = item
            self._variables["repeat"] = repeat_vars

        script = self._script._get_repeat_script(self._step)  # noqa: SLF001
        warned_too_many_loops = False

        async def async_run_sequence(iteration: int, extra_msg: str = "") -> None:
            self._log("Repeating %s: Iteration %i%s", description, iteration, extra_msg)
            with trace_path("sequence"):
                await self._async_run_script(script)

        if CONF_COUNT in repeat:
            count = repeat[CONF_COUNT]
            if isinstance(count, template.Template):
                try:
                    count = int(count.async_render(self._variables))
                except (exceptions.TemplateError, ValueError) as ex:
                    self._log(
                        "Error rendering %s repeat count template: %s",
                        self._script.name,
                        ex,
                        level=logging.ERROR,
                    )
                    raise _AbortScript from ex
            extra_msg = f" of {count}"
            for iteration in range(1, count + 1):
                set_repeat_var(iteration, count)
                await async_run_sequence(iteration, extra_msg)
                if self._stop.done():
                    break

        elif CONF_FOR_EACH in repeat:
            try:
                items = template.render_complex(repeat[CONF_FOR_EACH], self._variables)
            except (exceptions.TemplateError, ValueError) as ex:
                self._log(
                    "Error rendering %s repeat for each items template: %s",
                    self._script.name,
                    ex,
                    level=logging.ERROR,
                )
                raise _AbortScript from ex

            if not isinstance(items, list):
                self._log(
                    "Repeat 'for_each' must be a list of items in %s, got: %s",
                    self._script.name,
                    items,
                    level=logging.ERROR,
                )
                raise _AbortScript("Repeat 'for_each' must be a list of items")

            count = len(items)
            for iteration, item in enumerate(items, 1):
                set_repeat_var(iteration, count, item)
                extra_msg = f" of {count} with item: {item!r}"
                if self._stop.done():
                    break
                await async_run_sequence(iteration, extra_msg)

        elif CONF_WHILE in repeat:
            conditions = [
                await self._async_get_condition(config) for config in repeat[CONF_WHILE]
            ]
            for iteration in itertools.count(1):
                set_repeat_var(iteration)
                try:
                    if self._stop.done():
                        break
                    if not self._test_conditions(conditions, "while"):
                        break
                except exceptions.ConditionError as ex:
                    _LOGGER.warning("Error in 'while' evaluation:\n%s", ex)
                    break

                if iteration > 1:
                    if iteration > REPEAT_WARN_ITERATIONS:
                        if not warned_too_many_loops:
                            warned_too_many_loops = True
                            _LOGGER.warning(
                                "While condition %s in script `%s` looped %s times",
                                repeat[CONF_WHILE],
                                self._script.name,
                                REPEAT_WARN_ITERATIONS,
                            )

                        if iteration > REPEAT_TERMINATE_ITERATIONS:
                            _LOGGER.critical(
                                "While condition %s in script `%s` "
                                "terminated because it looped %s times",
                                repeat[CONF_WHILE],
                                self._script.name,
                                REPEAT_TERMINATE_ITERATIONS,
                            )
                            raise _AbortScript(
                                f"While condition {repeat[CONF_WHILE]} "
                                "terminated because it looped "
                                f" {REPEAT_TERMINATE_ITERATIONS} times"
                            )

                    # If the user creates a script with a tight loop,
                    # yield to the event loop so the system stays
                    # responsive while all the cpu time is consumed.
                    await asyncio.sleep(0)

                await async_run_sequence(iteration)

        elif CONF_UNTIL in repeat:
            conditions = [
                await self._async_get_condition(config) for config in repeat[CONF_UNTIL]
            ]
            for iteration in itertools.count(1):
                set_repeat_var(iteration)
                await async_run_sequence(iteration)
                try:
                    if self._stop.done():
                        break
                    if self._test_conditions(conditions, "until") in [True, None]:
                        break
                except exceptions.ConditionError as ex:
                    _LOGGER.warning("Error in 'until' evaluation:\n%s", ex)
                    break

                if iteration >= REPEAT_WARN_ITERATIONS:
                    if not warned_too_many_loops:
                        warned_too_many_loops = True
                        _LOGGER.warning(
                            "Until condition %s in script `%s` looped %s times",
                            repeat[CONF_UNTIL],
                            self._script.name,
                            REPEAT_WARN_ITERATIONS,
                        )

                    if iteration >= REPEAT_TERMINATE_ITERATIONS:
                        _LOGGER.critical(
                            "Until condition %s in script `%s` "
                            "terminated because it looped %s times",
                            repeat[CONF_UNTIL],
                            self._script.name,
                            REPEAT_TERMINATE_ITERATIONS,
                        )
                        raise _AbortScript(
                            f"Until condition {repeat[CONF_UNTIL]} "
                            "terminated because it looped "
                            f"{REPEAT_TERMINATE_ITERATIONS} times"
                        )

                # If the user creates a script with a tight loop,
                # yield to the event loop so the system stays responsive
                # while all the cpu time is consumed.
                await asyncio.sleep(0)

        if saved_repeat_vars:
            self._variables["repeat"] = saved_repeat_vars
        else:
            self._variables.pop("repeat", None)  # Not set if count = 0

    async def _async_choose_step(self) -> None:
        """Choose a sequence."""
        choose_data = await self._script._async_get_choose_data(self._step)  # noqa: SLF001

        with trace_path("choose"):
            for idx, (conditions, script) in enumerate(choose_data["choices"]):
                with trace_path(str(idx)):
                    try:
                        if self._test_conditions(conditions, "choose", "conditions"):
                            trace_set_result(choice=idx)
                            with trace_path("sequence"):
                                await self._async_run_script(script)
                                return
                    except exceptions.ConditionError as ex:
                        _LOGGER.warning("Error in 'choose' evaluation:\n%s", ex)

        if choose_data["default"] is not None:
            trace_set_result(choice="default")
            with trace_path(["default"]):
                await self._async_run_script(choose_data["default"])

    async def _async_if_step(self) -> None:
        """If sequence."""
        if_data = await self._script._async_get_if_data(self._step)  # noqa: SLF001

        test_conditions: bool | None = False
        try:
            with trace_path("if"):
                test_conditions = self._test_conditions(
                    if_data["if_conditions"], "if", "condition"
                )
        except exceptions.ConditionError as ex:
            _LOGGER.warning("Error in 'if' evaluation:\n%s", ex)

        if test_conditions:
            trace_set_result(choice="then")
            with trace_path("then"):
                await self._async_run_script(if_data["if_then"])
                return

        if if_data["if_else"] is not None:
            trace_set_result(choice="else")
            with trace_path("else"):
                await self._async_run_script(if_data["if_else"])

    @overload
    def _async_futures_with_timeout(
        self,
        timeout: float,
    ) -> tuple[
        list[asyncio.Future[None]],
        asyncio.TimerHandle,
        asyncio.Future[None],
    ]: ...

    @overload
    def _async_futures_with_timeout(
        self,
        timeout: None,
    ) -> tuple[
        list[asyncio.Future[None]],
        None,
        None,
    ]: ...

    def _async_futures_with_timeout(
        self,
        timeout: float | None,
    ) -> tuple[
        list[asyncio.Future[None]],
        asyncio.TimerHandle | None,
        asyncio.Future[None] | None,
    ]:
        """Return a list of futures to wait for.

        The list will contain the stop future.

        If timeout is set, a timeout future and handle will be created
        and will be added to the list of futures.
        """
        timeout_handle: asyncio.TimerHandle | None = None
        timeout_future: asyncio.Future[None] | None = None
        futures: list[asyncio.Future[None]] = [self._stop]
        if timeout:
            timeout_future = self._hass.loop.create_future()
            timeout_handle = self._hass.loop.call_later(
                timeout, _set_result_unless_done, timeout_future
            )
            futures.append(timeout_future)
        return futures, timeout_handle, timeout_future

    async def _async_wait_for_trigger_step(self) -> None:
        """Wait for a trigger event."""
        timeout = self._get_timeout_seconds_from_action()

        self._step_log("wait for trigger", timeout)

        variables = {**self._variables}
        self._variables["wait"] = {
            "remaining": timeout,
            "completed": False,
            "trigger": None,
        }
        trace_set_result(wait=self._variables["wait"])

        if timeout == 0:
            self._changed()
            self._async_handle_timeout()
            return

        futures, timeout_handle, timeout_future = self._async_futures_with_timeout(
            timeout
        )
        done = self._hass.loop.create_future()
        futures.append(done)

        async def async_done(
            variables: dict[str, Any], context: Context | None = None
        ) -> None:
            self._async_set_remaining_time_var(timeout_handle)
            self._variables["wait"]["completed"] = True
            self._variables["wait"]["trigger"] = variables["trigger"]
            _set_result_unless_done(done)

        def log_cb(level: int, msg: str, **kwargs: Any) -> None:
            self._log(msg, level=level, **kwargs)

        remove_triggers = await async_initialize_triggers(
            self._hass,
            self._action[CONF_WAIT_FOR_TRIGGER],
            async_done,
            self._script.domain,
            self._script.name,
            log_cb,
            variables=variables,
        )
        if not remove_triggers:
            return
        self._changed()
        await self._async_wait_with_optional_timeout(
            futures, timeout_handle, timeout_future, remove_triggers
        )

    def _async_handle_timeout(self) -> None:
        """Handle timeout."""
        self._variables["wait"]["remaining"] = 0.0
        if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
            self._log(_TIMEOUT_MSG)
            trace_set_result(wait=self._variables["wait"], timeout=True)
            raise _AbortScript from TimeoutError()

    async def _async_wait_with_optional_timeout(
        self,
        futures: list[asyncio.Future[None]],
        timeout_handle: asyncio.TimerHandle | None,
        timeout_future: asyncio.Future[None] | None,
        unsub: Callable[[], None],
    ) -> None:
        try:
            await asyncio.wait(futures, return_when=asyncio.FIRST_COMPLETED)
            if timeout_future and timeout_future.done():
                self._async_handle_timeout()
        finally:
            if timeout_future and not timeout_future.done() and timeout_handle:
                timeout_handle.cancel()

            unsub()

    async def _async_variables_step(self) -> None:
        """Set a variable value."""
        self._step_log("setting variables")
        self._variables = self._action[CONF_VARIABLES].async_render(
            self._hass, self._variables, render_as_defaults=False
        )

    async def _async_set_conversation_response_step(self) -> None:
        """Set conversation response."""
        self._step_log("setting conversation response")
        resp: template.Template | None = self._action[CONF_SET_CONVERSATION_RESPONSE]
        if resp is None:
            self._conversation_response = None
        else:
            self._conversation_response = resp.async_render(
                variables=self._variables, parse_result=False
            )
        trace_set_result(conversation_response=self._conversation_response)

    async def _async_stop_step(self) -> None:
        """Stop script execution."""
        stop = self._action[CONF_STOP]
        error = self._action.get(CONF_ERROR, False)
        trace_set_result(stop=stop, error=error)
        if error:
            self._log("Error script sequence: %s", stop)
            raise _AbortScript(stop)

        self._log("Stop script sequence: %s", stop)
        if CONF_RESPONSE_VARIABLE in self._action:
            try:
                response = self._variables[self._action[CONF_RESPONSE_VARIABLE]]
            except KeyError as ex:
                raise _AbortScript(
                    f"Response variable '{self._action[CONF_RESPONSE_VARIABLE]}' "
                    "is not defined"
                ) from ex
        else:
            response = None
        raise _StopScript(stop, response)

    @async_trace_path("sequence")
    async def _async_sequence_step(self) -> None:
        """Run a sequence."""
        sequence = await self._script._async_get_sequence_script(self._step)  # noqa: SLF001
        await self._async_run_script(sequence)

    @async_trace_path("parallel")
    async def _async_parallel_step(self) -> None:
        """Run a sequence in parallel."""
        scripts = await self._script._async_get_parallel_scripts(self._step)  # noqa: SLF001

        async def async_run_with_trace(idx: int, script: Script) -> None:
            """Run a script with a trace path."""
            trace_path_stack_cv.set(copy(trace_path_stack_cv.get()))
            with trace_path([str(idx), "sequence"]):
                await self._async_run_script(script)

        results = await asyncio.gather(
            *(async_run_with_trace(idx, script) for idx, script in enumerate(scripts)),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                raise result

    async def _async_run_script(self, script: Script) -> None:
        """Execute a script."""
        result = await self._async_run_long_action(
            self._hass.async_create_task_internal(
                script.async_run(self._variables, self._context), eager_start=True
            )
        )
        if result and result.conversation_response is not UNDEFINED:
            self._conversation_response = result.conversation_response


class _QueuedScriptRun(_ScriptRun):
    """Manage queued Script sequence run."""

    lock_acquired = False

    async def async_run(self) -> None:
        """Run script."""
        # Wait for previous run, if any, to finish by attempting to acquire the script's
        # shared lock. At the same time monitor if we've been told to stop.
        try:
            async with async_interrupt.interrupt(self._stop, ScriptStoppedError, None):
                await self._script._queue_lck.acquire()  # noqa: SLF001
        except ScriptStoppedError as ex:
            # If we've been told to stop, then just finish up.
            self._finish()
            raise asyncio.CancelledError from ex

        self.lock_acquired = True
        # We've acquired the lock so we can go ahead and start the run.
        await super().async_run()

    def _finish(self) -> None:
        if self.lock_acquired:
            self._script._queue_lck.release()  # noqa: SLF001
            self.lock_acquired = False
        super()._finish()


@callback
def _schedule_stop_scripts_after_shutdown(hass: HomeAssistant) -> None:
    """Stop running Script objects started after shutdown."""
    async_call_later(
        hass, _SHUTDOWN_MAX_WAIT, partial(_async_stop_scripts_after_shutdown, hass)
    )


async def _async_stop_scripts_after_shutdown(
    hass: HomeAssistant, point_in_time: datetime
) -> None:
    """Stop running Script objects started after shutdown."""
    hass.data[DATA_NEW_SCRIPT_RUNS_NOT_ALLOWED] = None
    running_scripts = [
        script for script in hass.data[DATA_SCRIPTS] if script["instance"].is_running
    ]
    if running_scripts:
        names = ", ".join([script["instance"].name for script in running_scripts])
        _LOGGER.warning("Stopping scripts running too long after shutdown: %s", names)
        await asyncio.gather(
            *(
                create_eager_task(script["instance"].async_stop(update_state=False))
                for script in running_scripts
            )
        )


async def _async_stop_scripts_at_shutdown(hass: HomeAssistant, event: Event) -> None:
    """Stop running Script objects started before shutdown."""
    _schedule_stop_scripts_after_shutdown(hass)

    running_scripts = [
        script
        for script in hass.data[DATA_SCRIPTS]
        if script["instance"].is_running and script["started_before_shutdown"]
    ]
    if running_scripts:
        names = ", ".join([script["instance"].name for script in running_scripts])
        _LOGGER.debug("Stopping scripts running at shutdown: %s", names)
        await asyncio.gather(
            *(
                create_eager_task(script["instance"].async_stop())
                for script in running_scripts
            )
        )


type _VarsType = dict[str, Any] | Mapping[str, Any] | MappingProxyType[str, Any]


def _referenced_extract_ids(data: Any, key: str, found: set[str]) -> None:
    """Extract referenced IDs."""
    # Data may not exist, or be a template
    if not isinstance(data, dict):
        return

    item_ids = data.get(key)

    if item_ids is None or isinstance(item_ids, template.Template):
        return

    if isinstance(item_ids, str):
        found.add(item_ids)
    else:
        for item_id in item_ids:
            found.add(item_id)


class _ChooseData(TypedDict):
    choices: list[tuple[list[ConditionCheckerType], Script]]
    default: Script | None


class _IfData(TypedDict):
    if_conditions: list[ConditionCheckerType]
    if_then: Script
    if_else: Script | None


@dataclass
class ScriptRunResult:
    """Container with the result of a script run."""

    conversation_response: str | None | UndefinedType
    service_response: ServiceResponse
    variables: dict[str, Any]


class Script:
    """Representation of a script."""

    def __init__(
        self,
        hass: HomeAssistant,
        sequence: Sequence[dict[str, Any]],
        name: str,
        domain: str,
        *,
        # Used in "Running <running_description>" log message
        change_listener: Callable[[], Any] | None = None,
        copy_variables: bool = False,
        log_exceptions: bool = True,
        logger: logging.Logger | None = None,
        max_exceeded: str = DEFAULT_MAX_EXCEEDED,
        max_runs: int = DEFAULT_MAX,
        running_description: str | None = None,
        script_mode: str = DEFAULT_SCRIPT_MODE,
        top_level: bool = True,
        variables: ScriptVariables | None = None,
    ) -> None:
        """Initialize the script."""
        if not (all_scripts := hass.data.get(DATA_SCRIPTS)):
            all_scripts = hass.data[DATA_SCRIPTS] = []
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, partial(_async_stop_scripts_at_shutdown, hass)
            )
        self.top_level = top_level
        if top_level:
            all_scripts.append(
                {"instance": self, "started_before_shutdown": not hass.is_stopping}
            )
        if DATA_SCRIPT_BREAKPOINTS not in hass.data:
            hass.data[DATA_SCRIPT_BREAKPOINTS] = {}

        self._hass = hass
        self.sequence = sequence
        self.name = name
        self.unique_id = f"{domain}.{name}-{id(self)}"
        self.domain = domain
        self.running_description = running_description or f"{domain} script"
        self._change_listener = change_listener
        self._change_listener_job = (
            None if change_listener is None else HassJob(change_listener)
        )

        self.script_mode = script_mode
        self._set_logger(logger)
        self._log_exceptions = log_exceptions

        self.last_action: str | None = None
        self.last_triggered: datetime | None = None

        self._runs: list[_ScriptRun] = []
        self.max_runs = max_runs
        self._max_exceeded = max_exceeded
        if script_mode == SCRIPT_MODE_QUEUED:
            self._queue_lck = asyncio.Lock()
        self._config_cache: dict[frozenset[tuple[str, str]], ConditionCheckerType] = {}
        self._repeat_script: dict[int, Script] = {}
        self._choose_data: dict[int, _ChooseData] = {}
        self._if_data: dict[int, _IfData] = {}
        self._parallel_scripts: dict[int, list[Script]] = {}
        self._sequence_scripts: dict[int, Script] = {}
        self.variables = variables
        self._variables_dynamic = template.is_complex(variables)
        self._copy_variables_on_run = copy_variables

    @property
    def change_listener(self) -> Callable[..., Any] | None:
        """Return the change_listener."""
        return self._change_listener

    @change_listener.setter
    def change_listener(self, change_listener: Callable[[], Any]) -> None:
        """Update the change_listener."""
        self._change_listener = change_listener
        if (
            self._change_listener_job is None
            or change_listener != self._change_listener_job.target
        ):
            self._change_listener_job = HassJob(change_listener)

    def _set_logger(self, logger: logging.Logger | None = None) -> None:
        if logger:
            self._logger = logger
        else:
            self._logger = logging.getLogger(f"{__name__}.{slugify(self.name)}")

    def update_logger(self, logger: logging.Logger | None = None) -> None:
        """Update logger."""
        self._set_logger(logger)
        for script in self._repeat_script.values():
            script.update_logger(self._logger)
        for parallel_scripts in self._parallel_scripts.values():
            for parallel_script in parallel_scripts:
                parallel_script.update_logger(self._logger)
        for choose_data in self._choose_data.values():
            for _, script in choose_data["choices"]:
                script.update_logger(self._logger)
            if choose_data["default"] is not None:
                choose_data["default"].update_logger(self._logger)
        for if_data in self._if_data.values():
            if_data["if_then"].update_logger(self._logger)
            if if_data["if_else"] is not None:
                if_data["if_else"].update_logger(self._logger)

    def _changed(self) -> None:
        if self._change_listener_job:
            self._hass.async_run_hass_job(self._change_listener_job)

    @callback
    def _chain_change_listener(self, sub_script: Script) -> None:
        if sub_script.is_running:
            self.last_action = sub_script.last_action
            self._changed()

    @property
    def is_running(self) -> bool:
        """Return true if script is on."""
        return len(self._runs) > 0

    @property
    def runs(self) -> int:
        """Return the number of current runs."""
        return len(self._runs)

    @property
    def supports_max(self) -> bool:
        """Return true if the current mode support max."""
        return self.script_mode in (SCRIPT_MODE_PARALLEL, SCRIPT_MODE_QUEUED)

    @cached_property
    def referenced_labels(self) -> set[str]:
        """Return a set of referenced labels."""
        referenced_labels: set[str] = set()
        Script._find_referenced_target(ATTR_LABEL_ID, referenced_labels, self.sequence)
        return referenced_labels

    @cached_property
    def referenced_floors(self) -> set[str]:
        """Return a set of referenced fooors."""
        referenced_floors: set[str] = set()
        Script._find_referenced_target(ATTR_FLOOR_ID, referenced_floors, self.sequence)
        return referenced_floors

    @cached_property
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""
        referenced_areas: set[str] = set()
        Script._find_referenced_target(ATTR_AREA_ID, referenced_areas, self.sequence)
        return referenced_areas

    @staticmethod
    def _find_referenced_target(
        target: Literal["area_id", "floor_id", "label_id"],
        referenced: set[str],
        sequence: Sequence[dict[str, Any]],
    ) -> None:
        """Find referenced target in a sequence."""
        for step in sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CALL_SERVICE:
                for data in (
                    step.get(CONF_TARGET),
                    step.get(CONF_SERVICE_DATA),
                    step.get(CONF_SERVICE_DATA_TEMPLATE),
                ):
                    _referenced_extract_ids(data, target, referenced)

            elif action == cv.SCRIPT_ACTION_CHOOSE:
                for choice in step[CONF_CHOOSE]:
                    Script._find_referenced_target(
                        target, referenced, choice[CONF_SEQUENCE]
                    )
                if CONF_DEFAULT in step:
                    Script._find_referenced_target(
                        target, referenced, step[CONF_DEFAULT]
                    )

            elif action == cv.SCRIPT_ACTION_IF:
                Script._find_referenced_target(target, referenced, step[CONF_THEN])
                if CONF_ELSE in step:
                    Script._find_referenced_target(target, referenced, step[CONF_ELSE])

            elif action == cv.SCRIPT_ACTION_PARALLEL:
                for script in step[CONF_PARALLEL]:
                    Script._find_referenced_target(
                        target, referenced, script[CONF_SEQUENCE]
                    )

    @cached_property
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""
        referenced_devices: set[str] = set()
        Script._find_referenced_devices(referenced_devices, self.sequence)
        return referenced_devices

    @staticmethod
    def _find_referenced_devices(
        referenced: set[str], sequence: Sequence[dict[str, Any]]
    ) -> None:
        for step in sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CALL_SERVICE:
                for data in (
                    step.get(CONF_TARGET),
                    step.get(CONF_SERVICE_DATA),
                    step.get(CONF_SERVICE_DATA_TEMPLATE),
                ):
                    _referenced_extract_ids(data, ATTR_DEVICE_ID, referenced)

            elif action == cv.SCRIPT_ACTION_CHECK_CONDITION:
                referenced |= condition.async_extract_devices(step)

            elif action == cv.SCRIPT_ACTION_DEVICE_AUTOMATION:
                referenced.add(step[CONF_DEVICE_ID])

            elif action == cv.SCRIPT_ACTION_CHOOSE:
                for choice in step[CONF_CHOOSE]:
                    for cond in choice[CONF_CONDITIONS]:
                        referenced |= condition.async_extract_devices(cond)
                    Script._find_referenced_devices(referenced, choice[CONF_SEQUENCE])
                if CONF_DEFAULT in step:
                    Script._find_referenced_devices(referenced, step[CONF_DEFAULT])

            elif action == cv.SCRIPT_ACTION_IF:
                for cond in step[CONF_IF]:
                    referenced |= condition.async_extract_devices(cond)
                Script._find_referenced_devices(referenced, step[CONF_THEN])
                if CONF_ELSE in step:
                    Script._find_referenced_devices(referenced, step[CONF_ELSE])

            elif action == cv.SCRIPT_ACTION_PARALLEL:
                for script in step[CONF_PARALLEL]:
                    Script._find_referenced_devices(referenced, script[CONF_SEQUENCE])

    @cached_property
    def referenced_entities(self) -> set[str]:
        """Return a set of referenced entities."""
        referenced_entities: set[str] = set()
        Script._find_referenced_entities(referenced_entities, self.sequence)
        return referenced_entities

    @staticmethod
    def _find_referenced_entities(
        referenced: set[str], sequence: Sequence[dict[str, Any]]
    ) -> None:
        for step in sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CALL_SERVICE:
                for data in (
                    step,
                    step.get(CONF_TARGET),
                    step.get(CONF_SERVICE_DATA),
                    step.get(CONF_SERVICE_DATA_TEMPLATE),
                ):
                    _referenced_extract_ids(data, ATTR_ENTITY_ID, referenced)

            elif action == cv.SCRIPT_ACTION_CHECK_CONDITION:
                referenced |= condition.async_extract_entities(step)

            elif action == cv.SCRIPT_ACTION_ACTIVATE_SCENE:
                referenced.add(step[CONF_SCENE])

            elif action == cv.SCRIPT_ACTION_CHOOSE:
                for choice in step[CONF_CHOOSE]:
                    for cond in choice[CONF_CONDITIONS]:
                        referenced |= condition.async_extract_entities(cond)
                    Script._find_referenced_entities(referenced, choice[CONF_SEQUENCE])
                if CONF_DEFAULT in step:
                    Script._find_referenced_entities(referenced, step[CONF_DEFAULT])

            elif action == cv.SCRIPT_ACTION_IF:
                for cond in step[CONF_IF]:
                    referenced |= condition.async_extract_entities(cond)
                Script._find_referenced_entities(referenced, step[CONF_THEN])
                if CONF_ELSE in step:
                    Script._find_referenced_entities(referenced, step[CONF_ELSE])

            elif action == cv.SCRIPT_ACTION_PARALLEL:
                for script in step[CONF_PARALLEL]:
                    Script._find_referenced_entities(referenced, script[CONF_SEQUENCE])

    def run(
        self, variables: _VarsType | None = None, context: Context | None = None
    ) -> None:
        """Run script."""
        asyncio.run_coroutine_threadsafe(
            self.async_run(variables, context), self._hass.loop
        ).result()

    async def async_run(
        self,
        run_variables: _VarsType | None = None,
        context: Context | None = None,
        started_action: Callable[..., Any] | None = None,
    ) -> ScriptRunResult | None:
        """Run script."""
        if context is None:
            self._log(
                "Running script requires passing in a context", level=logging.WARNING
            )
            context = Context()

        # Prevent spawning new script runs when Home Assistant is shutting down
        if DATA_NEW_SCRIPT_RUNS_NOT_ALLOWED in self._hass.data:
            self._log("Home Assistant is shutting down, starting script blocked")
            return None

        # Prevent spawning new script runs if not allowed by script mode
        if self.is_running:
            if self.script_mode == SCRIPT_MODE_SINGLE:
                if self._max_exceeded != "SILENT":
                    self._log("Already running", level=LOGSEVERITY[self._max_exceeded])
                script_execution_set("failed_single")
                return None
            if self.script_mode != SCRIPT_MODE_RESTART and self.runs == self.max_runs:
                if self._max_exceeded != "SILENT":
                    self._log(
                        "Maximum number of runs exceeded",
                        level=LOGSEVERITY[self._max_exceeded],
                    )
                script_execution_set("failed_max_runs")
                return None

        # If this is a top level Script then make a copy of the variables in case they
        # are read-only, but more importantly, so as not to leak any variables created
        # during the run back to the caller.
        if self.top_level:
            if self.variables:
                try:
                    variables = self.variables.async_render(
                        self._hass,
                        run_variables,
                    )
                except exceptions.TemplateError as err:
                    self._log("Error rendering variables: %s", err, level=logging.ERROR)
                    raise
            elif run_variables:
                variables = dict(run_variables)
            else:
                variables = {}

            variables["context"] = context
        elif self._copy_variables_on_run:
            # This is not the top level script, variables have been turned to a dict
            variables = cast(dict[str, Any], copy(run_variables))
        else:
            # This is not the top level script, variables have been turned to a dict
            variables = cast(dict[str, Any], run_variables)

        # Prevent non-allowed recursive calls which will cause deadlocks when we try to
        # stop (restart) or wait for (queued) our own script run.
        script_stack = script_stack_cv.get()
        if (
            self.script_mode in (SCRIPT_MODE_RESTART, SCRIPT_MODE_QUEUED)
            and script_stack is not None
            and self.unique_id in script_stack
        ):
            script_execution_set("disallowed_recursion_detected")
            formatted_stack = [
                f"- {name_id.partition('-')[0]}" for name_id in script_stack
            ]
            self._log(
                "Disallowed recursion detected, "
                f"{script_stack[-1].partition('-')[0]} tried to start "
                f"{self.domain}.{self.name} which is already running "
                "in the current execution path; "
                "Traceback (most recent call last):\n"
                f"{'\n'.join(formatted_stack)}",
                level=logging.WARNING,
            )
            return None

        if self.script_mode != SCRIPT_MODE_QUEUED:
            cls = _ScriptRun
        else:
            cls = _QueuedScriptRun
        run = cls(self._hass, self, variables, context, self._log_exceptions)
        has_existing_runs = bool(self._runs)
        self._runs.append(run)
        if self.script_mode == SCRIPT_MODE_RESTART and has_existing_runs:
            # When script mode is SCRIPT_MODE_RESTART, first add the new run and then
            # stop any other runs. If we stop other runs first, self.is_running will
            # return false after the other script runs were stopped until our task
            # resumes running. Its important that we check if there are existing
            # runs before sleeping as otherwise if two runs are started at the exact
            # same time they will cancel each other out.
            self._log("Restarting")
            await self.async_stop(update_state=False, spare=run)

        if started_action:
            started_action()
        self.last_triggered = utcnow()
        self._changed()

        try:
            return await asyncio.shield(create_eager_task(run.async_run()))
        except asyncio.CancelledError:
            await run.async_stop()
            self._changed()
            raise

    async def _async_stop(
        self, aws: list[asyncio.Task[None]], update_state: bool
    ) -> None:
        await asyncio.wait(aws)
        if update_state:
            self._changed()

    async def async_stop(
        self, update_state: bool = True, spare: _ScriptRun | None = None
    ) -> None:
        """Stop running script."""
        # Collect a list of script runs to stop. This must be done before calling
        # asyncio.shield as asyncio.shield yields to the event loop, which would cause
        # us to wait for script runs added after the call to async_stop.
        aws = [
            create_eager_task(run.async_stop()) for run in self._runs if run != spare
        ]
        if not aws:
            return
        await asyncio.shield(create_eager_task(self._async_stop(aws, update_state)))

    async def _async_get_condition(self, config: ConfigType) -> ConditionCheckerType:
        config_cache_key = frozenset((k, str(v)) for k, v in config.items())
        if not (cond := self._config_cache.get(config_cache_key)):
            cond = await condition.async_from_config(self._hass, config)
            self._config_cache[config_cache_key] = cond
        return cond

    def _prep_repeat_script(self, step: int) -> Script:
        action = self.sequence[step]
        step_name = action.get(CONF_ALIAS, f"Repeat at step {step + 1}")
        sub_script = Script(
            self._hass,
            action[CONF_REPEAT][CONF_SEQUENCE],
            f"{self.name}: {step_name}",
            self.domain,
            running_description=self.running_description,
            script_mode=SCRIPT_MODE_PARALLEL,
            max_runs=self.max_runs,
            logger=self._logger,
            top_level=False,
        )
        sub_script.change_listener = partial(self._chain_change_listener, sub_script)
        return sub_script

    def _get_repeat_script(self, step: int) -> Script:
        if not (sub_script := self._repeat_script.get(step)):
            sub_script = self._prep_repeat_script(step)
            self._repeat_script[step] = sub_script
        return sub_script

    async def _async_prep_choose_data(self, step: int) -> _ChooseData:
        action = self.sequence[step]
        step_name = action.get(CONF_ALIAS, f"Choose at step {step + 1}")
        choices = []
        for idx, choice in enumerate(action[CONF_CHOOSE], start=1):
            conditions = [
                await self._async_get_condition(config)
                for config in choice.get(CONF_CONDITIONS, [])
            ]
            choice_name = choice.get(CONF_ALIAS, f"choice {idx}")
            sub_script = Script(
                self._hass,
                choice[CONF_SEQUENCE],
                f"{self.name}: {step_name}: {choice_name}",
                self.domain,
                running_description=self.running_description,
                script_mode=SCRIPT_MODE_PARALLEL,
                max_runs=self.max_runs,
                logger=self._logger,
                top_level=False,
            )
            sub_script.change_listener = partial(
                self._chain_change_listener, sub_script
            )
            choices.append((conditions, sub_script))

        default_script: Script | None
        if CONF_DEFAULT in action:
            default_script = Script(
                self._hass,
                action[CONF_DEFAULT],
                f"{self.name}: {step_name}: default",
                self.domain,
                running_description=self.running_description,
                script_mode=SCRIPT_MODE_PARALLEL,
                max_runs=self.max_runs,
                logger=self._logger,
                top_level=False,
            )
            default_script.change_listener = partial(
                self._chain_change_listener, default_script
            )
        else:
            default_script = None

        return {"choices": choices, "default": default_script}

    async def _async_get_choose_data(self, step: int) -> _ChooseData:
        if not (choose_data := self._choose_data.get(step)):
            choose_data = await self._async_prep_choose_data(step)
            self._choose_data[step] = choose_data
        return choose_data

    async def _async_prep_if_data(self, step: int) -> _IfData:
        """Prepare data for an if statement."""
        action = self.sequence[step]
        step_name = action.get(CONF_ALIAS, f"If at step {step + 1}")

        conditions = [
            await self._async_get_condition(config) for config in action[CONF_IF]
        ]

        then_script = Script(
            self._hass,
            action[CONF_THEN],
            f"{self.name}: {step_name}",
            self.domain,
            running_description=self.running_description,
            script_mode=SCRIPT_MODE_PARALLEL,
            max_runs=self.max_runs,
            logger=self._logger,
            top_level=False,
        )
        then_script.change_listener = partial(self._chain_change_listener, then_script)

        if CONF_ELSE in action:
            else_script = Script(
                self._hass,
                action[CONF_ELSE],
                f"{self.name}: {step_name}",
                self.domain,
                running_description=self.running_description,
                script_mode=SCRIPT_MODE_PARALLEL,
                max_runs=self.max_runs,
                logger=self._logger,
                top_level=False,
            )
            else_script.change_listener = partial(
                self._chain_change_listener, else_script
            )
        else:
            else_script = None

        return _IfData(
            if_conditions=conditions,
            if_then=then_script,
            if_else=else_script,
        )

    async def _async_get_if_data(self, step: int) -> _IfData:
        if not (if_data := self._if_data.get(step)):
            if_data = await self._async_prep_if_data(step)
            self._if_data[step] = if_data
        return if_data

    async def _async_prep_parallel_scripts(self, step: int) -> list[Script]:
        action = self.sequence[step]
        step_name = action.get(CONF_ALIAS, f"Parallel action at step {step + 1}")
        parallel_scripts: list[Script] = []
        for idx, parallel_script in enumerate(action[CONF_PARALLEL], start=1):
            parallel_name = parallel_script.get(CONF_ALIAS, f"parallel {idx}")
            parallel_script = Script(
                self._hass,
                parallel_script[CONF_SEQUENCE],
                f"{self.name}: {step_name}: {parallel_name}",
                self.domain,
                running_description=self.running_description,
                script_mode=SCRIPT_MODE_PARALLEL,
                max_runs=self.max_runs,
                logger=self._logger,
                top_level=False,
                copy_variables=True,
            )
            parallel_script.change_listener = partial(
                self._chain_change_listener, parallel_script
            )
            parallel_scripts.append(parallel_script)

        return parallel_scripts

    async def _async_get_parallel_scripts(self, step: int) -> list[Script]:
        if not (parallel_scripts := self._parallel_scripts.get(step)):
            parallel_scripts = await self._async_prep_parallel_scripts(step)
            self._parallel_scripts[step] = parallel_scripts
        return parallel_scripts

    async def _async_prep_sequence_script(self, step: int) -> Script:
        """Prepare a sequence script."""
        action = self.sequence[step]
        step_name = action.get(CONF_ALIAS, f"Sequence action at step {step + 1}")

        sequence_script = Script(
            self._hass,
            action[CONF_SEQUENCE],
            f"{self.name}: {step_name}",
            self.domain,
            running_description=self.running_description,
            script_mode=SCRIPT_MODE_PARALLEL,
            max_runs=self.max_runs,
            logger=self._logger,
            top_level=False,
        )
        sequence_script.change_listener = partial(
            self._chain_change_listener, sequence_script
        )

        return sequence_script

    async def _async_get_sequence_script(self, step: int) -> Script:
        """Get a (cached) sequence script."""
        if not (sequence_script := self._sequence_scripts.get(step)):
            sequence_script = await self._async_prep_sequence_script(step)
            self._sequence_scripts[step] = sequence_script
        return sequence_script

    def _log(
        self, msg: str, *args: Any, level: int = logging.INFO, **kwargs: Any
    ) -> None:
        msg = f"%s: {msg}"
        args = (self.name, *args)

        if level == _LOG_EXCEPTION:
            self._logger.exception(msg, *args, **kwargs)
        else:
            self._logger.log(level, msg, *args, **kwargs)


@callback
def breakpoint_clear(
    hass: HomeAssistant, key: str, run_id: str | None, node: str
) -> None:
    """Clear a breakpoint."""
    run_id = run_id or RUN_ID_ANY
    breakpoints = hass.data[DATA_SCRIPT_BREAKPOINTS]
    if key not in breakpoints or run_id not in breakpoints[key]:
        return
    breakpoints[key][run_id].discard(node)


@callback
def breakpoint_clear_all(hass: HomeAssistant) -> None:
    """Clear all breakpoints."""
    hass.data[DATA_SCRIPT_BREAKPOINTS] = {}


@callback
def breakpoint_set(
    hass: HomeAssistant, key: str, run_id: str | None, node: str
) -> None:
    """Set a breakpoint."""
    run_id = run_id or RUN_ID_ANY
    breakpoints = hass.data[DATA_SCRIPT_BREAKPOINTS]
    if key not in breakpoints:
        breakpoints[key] = {}
    if run_id not in breakpoints[key]:
        breakpoints[key][run_id] = set()
    breakpoints[key][run_id].add(node)


@callback
def breakpoint_list(hass: HomeAssistant) -> list[dict[str, Any]]:
    """List breakpoints."""
    breakpoints = hass.data[DATA_SCRIPT_BREAKPOINTS]

    return [
        {"key": key, "run_id": run_id, "node": node}
        for key in breakpoints
        for run_id in breakpoints[key]
        for node in breakpoints[key][run_id]
    ]


@callback
def debug_continue(hass: HomeAssistant, key: str, run_id: str) -> None:
    """Continue execution of a halted script."""
    # Clear any wildcard breakpoint
    breakpoint_clear(hass, key, run_id, NODE_ANY)

    signal = SCRIPT_DEBUG_CONTINUE_STOP.format(key, run_id)
    async_dispatcher_send_internal(hass, signal, "continue")


@callback
def debug_step(hass: HomeAssistant, key: str, run_id: str) -> None:
    """Single step a halted script."""
    # Set a wildcard breakpoint
    breakpoint_set(hass, key, run_id, NODE_ANY)

    signal = SCRIPT_DEBUG_CONTINUE_STOP.format(key, run_id)
    async_dispatcher_send_internal(hass, signal, "continue")


@callback
def debug_stop(hass: HomeAssistant, key: str, run_id: str) -> None:
    """Stop execution of a running or halted script."""
    signal = SCRIPT_DEBUG_CONTINUE_STOP.format(key, run_id)
    async_dispatcher_send_internal(hass, signal, "stop")
