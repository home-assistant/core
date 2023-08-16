"""Helpers to execute scripts."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from copy import copy
from datetime import datetime, timedelta
from functools import partial
import itertools
import logging
from types import MappingProxyType
from typing import Any, TypedDict, TypeVar, cast

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components import scene
from homeassistant.components.device_automation import action as device_action
from homeassistant.components.logger import LOGSEVERITY
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
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
    SupportsResponse,
    callback,
)
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from . import condition, config_validation as cv, service, template
from .condition import ConditionCheckerType, trace_condition_function
from .dispatcher import async_dispatcher_connect, async_dispatcher_send
from .event import async_call_later, async_track_template
from .script_variables import ScriptVariables
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
from .typing import ConfigType

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

_T = TypeVar("_T")

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
_MAX_EXCEEDED_CHOICES = list(LOGSEVERITY) + ["SILENT"]
DEFAULT_MAX_EXCEEDED = "WARNING"

ATTR_CUR = "current"
ATTR_MAX = "max"

DATA_SCRIPTS = "helpers.script"
DATA_SCRIPT_BREAKPOINTS = "helpers.script_breakpoints"
DATA_NEW_SCRIPT_RUNS_NOT_ALLOWED = "helpers.script_not_allowed"
RUN_ID_ANY = "*"
NODE_ANY = "*"

_LOGGER = logging.getLogger(__name__)

_LOG_EXCEPTION = logging.ERROR + 1
_TIMEOUT_MSG = "Timeout reached, abort script."

_SHUTDOWN_MAX_WAIT = 60
_SERVICE_CALL_LIMIT = 10

ACTION_TRACE_NODE_MAX_LEN = 20  # Max length of a trace node for repeated actions

SCRIPT_BREAKPOINT_HIT = "script_breakpoint_hit"
SCRIPT_DEBUG_CONTINUE_STOP = "script_debug_continue_stop_{}_{}"
SCRIPT_DEBUG_CONTINUE_ALL = "script_debug_continue_all"

script_stack_cv: ContextVar[list[int] | None] = ContextVar("script_stack", default=None)


def action_trace_append(variables, path):
    """Append a TraceElement to trace[path]."""
    trace_element = TraceElement(variables, path)
    trace_append_element(trace_element, ACTION_TRACE_NODE_MAX_LEN)
    return trace_element


@asynccontextmanager
async def trace_action(hass, script_run, stop, variables):
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
            async_dispatcher_send(hass, SCRIPT_BREAKPOINT_HIT, key, run_id, path)

            done = asyncio.Event()

            @callback
            def async_continue_stop(command=None):
                if command == "stop":
                    stop.set()
                done.set()

            signal = SCRIPT_DEBUG_CONTINUE_STOP.format(key, run_id)
            remove_signal1 = async_dispatcher_connect(hass, signal, async_continue_stop)
            remove_signal2 = async_dispatcher_connect(
                hass, SCRIPT_DEBUG_CONTINUE_ALL, async_continue_stop
            )

            tasks = [hass.async_create_task(flag.wait()) for flag in (stop, done)]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in tasks:
                task.cancel()
            remove_signal1()
            remove_signal2()

    try:
        yield trace_element
    except _AbortScript as ex:
        trace_element.set_error(ex.__cause__ or ex)
        raise ex
    except _ConditionFail as ex:
        # Clear errors which may have been set when evaluating the condition
        trace_element.set_error(None)
        raise ex
    except _StopScript as ex:
        raise ex
    except Exception as ex:
        trace_element.set_error(ex)
        raise ex
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
    cv.SCRIPT_ACTION_CALL_SERVICE,
    cv.SCRIPT_ACTION_DELAY,
    cv.SCRIPT_ACTION_WAIT_TEMPLATE,
    cv.SCRIPT_ACTION_FIRE_EVENT,
    cv.SCRIPT_ACTION_ACTIVATE_SCENE,
    cv.SCRIPT_ACTION_VARIABLES,
    cv.SCRIPT_ACTION_STOP,
)


async def async_validate_actions_config(
    hass: HomeAssistant, actions: list[ConfigType]
) -> list[ConfigType]:
    """Validate a list of actions."""
    return await asyncio.gather(
        *(async_validate_action_config(hass, action) for action in actions)
    )


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
        self._action: dict[str, Any] | None = None
        self._stop = asyncio.Event()
        self._stopped = asyncio.Event()

    def _changed(self) -> None:
        if not self._stop.is_set():
            self._script._changed()  # pylint: disable=protected-access

    async def _async_get_condition(self, config):
        # pylint: disable-next=protected-access
        return await self._script._async_get_condition(config)

    def _log(
        self, msg: str, *args: Any, level: int = logging.INFO, **kwargs: Any
    ) -> None:
        self._script._log(  # pylint: disable=protected-access
            msg, *args, level=level, **kwargs
        )

    def _step_log(self, default_message, timeout=None):
        self._script.last_action = self._action.get(CONF_ALIAS, default_message)
        _timeout = (
            "" if timeout is None else f" (timeout: {timedelta(seconds=timeout)})"
        )
        self._log("Executing step %s%s", self._script.last_action, _timeout)

    async def async_run(self) -> ServiceResponse:
        """Run script."""
        # Push the script to the script execution stack
        if (script_stack := script_stack_cv.get()) is None:
            script_stack = []
            script_stack_cv.set(script_stack)
        script_stack.append(id(self._script))
        response = None

        try:
            self._log("Running %s", self._script.running_description)
            for self._step, self._action in enumerate(self._script.sequence):
                if self._stop.is_set():
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
            response = err.response

            # Let the _StopScript bubble up if this is a sub-script
            if not self._script.top_level:
                # We already consumed the response, do not pass it on
                err.response = None
                raise err
        except Exception:
            script_execution_set("error")
            raise
        finally:
            # Pop the script from the script execution stack
            script_stack.pop()
            self._finish()

        return response

    async def _async_step(self, log_exceptions):
        continue_on_error = self._action.get(CONF_CONTINUE_ON_ERROR, False)

        with trace_path(str(self._step)):
            async with trace_action(self._hass, self, self._stop, self._variables):
                if self._stop.is_set():
                    return

                action = cv.determine_script_action(self._action)

                if not self._action.get(CONF_ENABLED, True):
                    self._log(
                        "Skipped disabled step %s", self._action.get(CONF_ALIAS, action)
                    )
                    trace_set_result(enabled=False)
                    return

                try:
                    handler = f"_async_{action}_step"
                    await getattr(self, handler)()
                except Exception as ex:  # pylint: disable=broad-except
                    self._handle_exception(
                        ex, continue_on_error, self._log_exceptions or log_exceptions
                    )

    def _finish(self) -> None:
        self._script._runs.remove(self)  # pylint: disable=protected-access
        if not self._script.is_running:
            self._script.last_action = None
        self._changed()
        self._stopped.set()

    async def async_stop(self) -> None:
        """Stop script run."""
        self._stop.set()
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

    def _log_exception(self, exception):
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

    def _get_pos_time_period_template(self, key):
        try:
            return cv.positive_time_period(
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

    async def _async_delay_step(self):
        """Handle delay."""
        delay = self._get_pos_time_period_template(CONF_DELAY)

        self._step_log(f"delay {delay}")

        delay = delay.total_seconds()
        self._changed()
        trace_set_result(delay=delay, done=False)
        try:
            async with asyncio.timeout(delay):
                await self._stop.wait()
        except asyncio.TimeoutError:
            trace_set_result(delay=delay, done=True)

    async def _async_wait_template_step(self):
        """Handle a wait template."""
        if CONF_TIMEOUT in self._action:
            timeout = self._get_pos_time_period_template(CONF_TIMEOUT).total_seconds()
        else:
            timeout = None

        self._step_log("wait template", timeout)

        self._variables["wait"] = {"remaining": timeout, "completed": False}
        trace_set_result(wait=self._variables["wait"])

        wait_template = self._action[CONF_WAIT_TEMPLATE]
        wait_template.hass = self._hass

        # check if condition already okay
        if condition.async_template(self._hass, wait_template, self._variables, False):
            self._variables["wait"]["completed"] = True
            return

        @callback
        def async_script_wait(entity_id, from_s, to_s):
            """Handle script after template condition is true."""
            # pylint: disable=protected-access
            wait_var = self._variables["wait"]
            if to_context and to_context._when:
                wait_var["remaining"] = to_context._when - self._hass.loop.time()
            else:
                wait_var["remaining"] = timeout
            wait_var["completed"] = True
            done.set()

        to_context = None
        unsub = async_track_template(
            self._hass, wait_template, async_script_wait, self._variables
        )

        self._changed()
        done = asyncio.Event()
        tasks = [
            self._hass.async_create_task(flag.wait()) for flag in (self._stop, done)
        ]
        try:
            async with asyncio.timeout(timeout) as to_context:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError as ex:
            self._variables["wait"]["remaining"] = 0.0
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                trace_set_result(wait=self._variables["wait"], timeout=True)
                raise _AbortScript from ex
        finally:
            for task in tasks:
                task.cancel()
            unsub()

    async def _async_run_long_action(
        self, long_task: asyncio.Task[_T], timeout: float | None = None
    ) -> _T | None:
        """Run a long task while monitoring for stop request."""

        async def async_cancel_long_task() -> None:
            # Stop long task and wait for it to finish.
            long_task.cancel()
            with suppress(Exception):
                await long_task

        # Wait for long task while monitoring for a stop request.
        stop_task = self._hass.async_create_task(self._stop.wait())
        try:
            await asyncio.wait(
                {long_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout,
            )
        # If our task is cancelled, then cancel long task, too. Note that if long task
        # is cancelled otherwise the CancelledError exception will not be raised to
        # here due to the call to asyncio.wait(). Rather we'll check for that below.
        except asyncio.CancelledError:
            await async_cancel_long_task()
            raise
        finally:
            stopped = stop_task.done()
            stop_task.cancel()
        if long_task.cancelled():
            raise asyncio.CancelledError
        if long_task.done():
            # Propagate any exceptions that occurred.
            return long_task.result()
        # Stopped or timed out before long task completed, so cancel it.
        await async_cancel_long_task()
        if stopped:
            return None
        raise asyncio.TimeoutError("Timeout while running task")

    async def _async_call_service_step(self):
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
        # If this might start a script then disable the call timeout.
        # Otherwise use the normal service call limit.
        if running_script:
            limit = None
        else:
            limit = _SERVICE_CALL_LIMIT
        trace_set_result(params=params, running_script=running_script)
        response_data = await self._async_run_long_action(
            self._hass.async_create_task(
                self._hass.services.async_call(
                    **params,
                    blocking=True,
                    context=self._context,
                    return_response=return_response,
                )
            ),
            timeout=limit,
        )
        if response_variable:
            self._variables[response_variable] = response_data

    async def _async_device_step(self):
        """Perform the device automation specified in the action."""
        self._step_log("device automation")
        await device_action.async_call_action_from_config(
            self._hass, self._action, self._variables, self._context
        )

    async def _async_scene_step(self):
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

    async def _async_event_step(self):
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
        self._hass.bus.async_fire(
            self._action[CONF_EVENT], event_data, context=self._context
        )

    async def _async_condition_step(self):
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

    def _test_conditions(self, conditions, name, condition_path=None):
        if condition_path is None:
            condition_path = name

        @trace_condition_function
        def traced_test_conditions(hass, variables):
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

        result = traced_test_conditions(self._hass, self._variables)
        return result

    @async_trace_path("repeat")
    async def _async_repeat_step(self):  # noqa: C901
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

        # pylint: disable-next=protected-access
        script = self._script._get_repeat_script(self._step)

        async def async_run_sequence(iteration, extra_msg=""):
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
                if self._stop.is_set():
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
                extra_msg = f" of {count} with item: {repr(item)}"
                if self._stop.is_set():
                    break
                await async_run_sequence(iteration, extra_msg)

        elif CONF_WHILE in repeat:
            conditions = [
                await self._async_get_condition(config) for config in repeat[CONF_WHILE]
            ]
            for iteration in itertools.count(1):
                set_repeat_var(iteration)
                try:
                    if self._stop.is_set():
                        break
                    if not self._test_conditions(conditions, "while"):
                        break
                except exceptions.ConditionError as ex:
                    _LOGGER.warning("Error in 'while' evaluation:\n%s", ex)
                    break

                await async_run_sequence(iteration)

        elif CONF_UNTIL in repeat:
            conditions = [
                await self._async_get_condition(config) for config in repeat[CONF_UNTIL]
            ]
            for iteration in itertools.count(1):
                set_repeat_var(iteration)
                await async_run_sequence(iteration)
                try:
                    if self._stop.is_set():
                        break
                    if self._test_conditions(conditions, "until") in [True, None]:
                        break
                except exceptions.ConditionError as ex:
                    _LOGGER.warning("Error in 'until' evaluation:\n%s", ex)
                    break

        if saved_repeat_vars:
            self._variables["repeat"] = saved_repeat_vars
        else:
            self._variables.pop("repeat", None)  # Not set if count = 0

    async def _async_choose_step(self) -> None:
        """Choose a sequence."""
        # pylint: disable=protected-access
        choose_data = await self._script._async_get_choose_data(self._step)

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
        # pylint: disable=protected-access
        if_data = await self._script._async_get_if_data(self._step)

        test_conditions = False
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

    async def _async_wait_for_trigger_step(self):
        """Wait for a trigger event."""
        if CONF_TIMEOUT in self._action:
            timeout = self._get_pos_time_period_template(CONF_TIMEOUT).total_seconds()
        else:
            timeout = None

        self._step_log("wait for trigger", timeout)

        variables = {**self._variables}
        self._variables["wait"] = {"remaining": timeout, "trigger": None}
        trace_set_result(wait=self._variables["wait"])

        done = asyncio.Event()

        async def async_done(variables, context=None):
            # pylint: disable=protected-access
            wait_var = self._variables["wait"]
            if to_context and to_context._when:
                wait_var["remaining"] = to_context._when - self._hass.loop.time()
            else:
                wait_var["remaining"] = timeout
            wait_var["trigger"] = variables["trigger"]
            done.set()

        def log_cb(level, msg, **kwargs):
            self._log(msg, level=level, **kwargs)

        to_context = None
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
        tasks = [
            self._hass.async_create_task(flag.wait()) for flag in (self._stop, done)
        ]
        try:
            async with asyncio.timeout(timeout) as to_context:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError as ex:
            self._variables["wait"]["remaining"] = 0.0
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                trace_set_result(wait=self._variables["wait"], timeout=True)
                raise _AbortScript from ex
        finally:
            for task in tasks:
                task.cancel()
            remove_triggers()

    async def _async_variables_step(self):
        """Set a variable value."""
        self._step_log("setting variables")
        self._variables = self._action[CONF_VARIABLES].async_render(
            self._hass, self._variables, render_as_defaults=False
        )

    async def _async_stop_step(self):
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

    @async_trace_path("parallel")
    async def _async_parallel_step(self) -> None:
        """Run a sequence in parallel."""
        # pylint: disable=protected-access
        scripts = await self._script._async_get_parallel_scripts(self._step)

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
        await self._async_run_long_action(
            self._hass.async_create_task(
                script.async_run(self._variables, self._context)
            )
        )


class _QueuedScriptRun(_ScriptRun):
    """Manage queued Script sequence run."""

    lock_acquired = False

    async def async_run(self) -> None:
        """Run script."""
        # Wait for previous run, if any, to finish by attempting to acquire the script's
        # shared lock. At the same time monitor if we've been told to stop.
        lock_task = self._hass.async_create_task(
            self._script._queue_lck.acquire()  # pylint: disable=protected-access
        )
        stop_task = self._hass.async_create_task(self._stop.wait())
        try:
            await asyncio.wait(
                {lock_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            self._finish()
            raise
        else:
            self.lock_acquired = lock_task.done() and not lock_task.cancelled()
        finally:
            lock_task.cancel()
            stop_task.cancel()

        # If we've been told to stop, then just finish up. Otherwise, we've acquired the
        # lock so we can go ahead and start the run.
        if self._stop.is_set():
            self._finish()
        else:
            await super().async_run()

    def _finish(self) -> None:
        # pylint: disable=protected-access
        if self.lock_acquired:
            self._script._queue_lck.release()
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
                script["instance"].async_stop(update_state=False)
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
            *(script["instance"].async_stop() for script in running_scripts)
        )


_VarsType = dict[str, Any] | MappingProxyType


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
        change_listener: Callable[..., Any] | None = None,
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
        template.attach(hass, self.sequence)
        self.name = name
        self.domain = domain
        self.running_description = running_description or f"{domain} script"
        self._change_listener = change_listener
        self._change_listener_job = (
            None if change_listener is None else HassJob(change_listener)
        )

        self.script_mode = script_mode
        self._set_logger(logger)
        self._log_exceptions = log_exceptions

        self.last_action = None
        self.last_triggered: datetime | None = None

        self._runs: list[_ScriptRun] = []
        self.max_runs = max_runs
        self._max_exceeded = max_exceeded
        if script_mode == SCRIPT_MODE_QUEUED:
            self._queue_lck = asyncio.Lock()
        self._config_cache: dict[set[tuple], Callable[..., bool]] = {}
        self._repeat_script: dict[int, Script] = {}
        self._choose_data: dict[int, _ChooseData] = {}
        self._if_data: dict[int, _IfData] = {}
        self._parallel_scripts: dict[int, list[Script]] = {}
        self._referenced_entities: set[str] | None = None
        self._referenced_devices: set[str] | None = None
        self._referenced_areas: set[str] | None = None
        self.variables = variables
        self._variables_dynamic = template.is_complex(variables)
        if self._variables_dynamic:
            template.attach(hass, variables)
        self._copy_variables_on_run = copy_variables

    @property
    def change_listener(self) -> Callable[..., Any] | None:
        """Return the change_listener."""
        return self._change_listener

    @change_listener.setter
    def change_listener(self, change_listener: Callable[..., Any]) -> None:
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

    @property
    def referenced_areas(self) -> set[str]:
        """Return a set of referenced areas."""
        if self._referenced_areas is not None:
            return self._referenced_areas

        self._referenced_areas = set()
        Script._find_referenced_areas(self._referenced_areas, self.sequence)
        return self._referenced_areas

    @staticmethod
    def _find_referenced_areas(
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
                    _referenced_extract_ids(data, ATTR_AREA_ID, referenced)

            elif action == cv.SCRIPT_ACTION_CHOOSE:
                for choice in step[CONF_CHOOSE]:
                    Script._find_referenced_areas(referenced, choice[CONF_SEQUENCE])
                if CONF_DEFAULT in step:
                    Script._find_referenced_areas(referenced, step[CONF_DEFAULT])

            elif action == cv.SCRIPT_ACTION_IF:
                Script._find_referenced_areas(referenced, step[CONF_THEN])
                if CONF_ELSE in step:
                    Script._find_referenced_areas(referenced, step[CONF_ELSE])

            elif action == cv.SCRIPT_ACTION_PARALLEL:
                for script in step[CONF_PARALLEL]:
                    Script._find_referenced_areas(referenced, script[CONF_SEQUENCE])

    @property
    def referenced_devices(self) -> set[str]:
        """Return a set of referenced devices."""
        if self._referenced_devices is not None:
            return self._referenced_devices

        self._referenced_devices = set()
        Script._find_referenced_devices(self._referenced_devices, self.sequence)
        return self._referenced_devices

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

    @property
    def referenced_entities(self) -> set[str]:
        """Return a set of referenced entities."""
        if self._referenced_entities is not None:
            return self._referenced_entities

        self._referenced_entities = set()
        Script._find_referenced_entities(self._referenced_entities, self.sequence)
        return self._referenced_entities

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
    ) -> ServiceResponse:
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
            variables = cast(dict, copy(run_variables))
        else:
            variables = cast(dict, run_variables)

        # Prevent non-allowed recursive calls which will cause deadlocks when we try to
        # stop (restart) or wait for (queued) our own script run.
        script_stack = script_stack_cv.get()
        if (
            self.script_mode in (SCRIPT_MODE_RESTART, SCRIPT_MODE_QUEUED)
            and (script_stack := script_stack_cv.get()) is not None
            and id(self) in script_stack
        ):
            script_execution_set("disallowed_recursion_detected")
            self._log("Disallowed recursion detected", level=logging.WARNING)
            return None

        if self.script_mode != SCRIPT_MODE_QUEUED:
            cls = _ScriptRun
        else:
            cls = _QueuedScriptRun
        run = cls(
            self._hass, self, cast(dict, variables), context, self._log_exceptions
        )
        self._runs.append(run)
        if self.script_mode == SCRIPT_MODE_RESTART:
            # When script mode is SCRIPT_MODE_RESTART, first add the new run and then
            # stop any other runs. If we stop other runs first, self.is_running will
            # return false after the other script runs were stopped until our task
            # resumes running.
            self._log("Restarting")
            await self.async_stop(update_state=False, spare=run)

        if started_action:
            self._hass.async_run_job(started_action)
        self.last_triggered = utcnow()
        self._changed()

        try:
            return await asyncio.shield(run.async_run())
        except asyncio.CancelledError:
            script_execution_set("cancelled")
            await run.async_stop()
            self._changed()
            raise

    async def _async_stop(
        self, aws: list[asyncio.Task], update_state: bool, spare: _ScriptRun | None
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
            asyncio.create_task(run.async_stop()) for run in self._runs if run != spare
        ]
        if not aws:
            return
        await asyncio.shield(self._async_stop(aws, update_state, spare))

    async def _async_get_condition(self, config):
        if isinstance(config, template.Template):
            config_cache_key = config.template
        else:
            config_cache_key = frozenset((k, str(v)) for k, v in config.items())
        if not (cond := self._config_cache.get(config_cache_key)):
            cond = await condition.async_from_config(self._hass, config)
            self._config_cache[config_cache_key] = cond
        return cond

    def _prep_repeat_script(self, step: int) -> Script:
        action = self.sequence[step]
        step_name = action.get(CONF_ALIAS, f"Repeat at step {step+1}")
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
        step_name = action.get(CONF_ALIAS, f"Choose at step {step+1}")
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
        step_name = action.get(CONF_ALIAS, f"If at step {step+1}")

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
        step_name = action.get(CONF_ALIAS, f"Parallel action at step {step+1}")
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
def breakpoint_clear(hass, key, run_id, node):
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
def breakpoint_set(hass, key, run_id, node):
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
def debug_continue(hass, key, run_id):
    """Continue execution of a halted script."""
    # Clear any wildcard breakpoint
    breakpoint_clear(hass, key, run_id, NODE_ANY)

    signal = SCRIPT_DEBUG_CONTINUE_STOP.format(key, run_id)
    async_dispatcher_send(hass, signal, "continue")


@callback
def debug_step(hass, key, run_id):
    """Single step a halted script."""
    # Set a wildcard breakpoint
    breakpoint_set(hass, key, run_id, NODE_ANY)

    signal = SCRIPT_DEBUG_CONTINUE_STOP.format(key, run_id)
    async_dispatcher_send(hass, signal, "continue")


@callback
def debug_stop(hass, key, run_id):
    """Stop execution of a running or halted script."""
    signal = SCRIPT_DEBUG_CONTINUE_STOP.format(key, run_id)
    async_dispatcher_send(hass, signal, "stop")
