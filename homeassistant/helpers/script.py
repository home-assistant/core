"""Helpers to execute scripts."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from functools import partial
import itertools
import logging
from types import MappingProxyType
from typing import Any, Callable, Dict, TypedDict, Union, cast

import async_timeout
import voluptuous as vol

from homeassistant import exceptions
from homeassistant.components import device_automation, scene
from homeassistant.components.logger import LOGSEVERITY
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_ALIAS,
    CONF_CHOOSE,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_CONTINUE_ON_TIMEOUT,
    CONF_COUNT,
    CONF_DEFAULT,
    CONF_DELAY,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_EVENT_DATA,
    CONF_EVENT_DATA_TEMPLATE,
    CONF_MODE,
    CONF_REPEAT,
    CONF_SCENE,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_TARGET,
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
    SERVICE_CALL_LIMIT,
    Context,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import condition, config_validation as cv, service, template
from homeassistant.helpers.condition import (
    ConditionCheckerType,
    trace_condition_function,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_call_later, async_track_template
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.trace import script_execution_set
from homeassistant.helpers.trigger import (
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from .trace import (
    TraceElement,
    async_trace_path,
    trace_append_element,
    trace_id_get,
    trace_path,
    trace_path_get,
    trace_set_result,
    trace_stack_cv,
    trace_stack_pop,
    trace_stack_push,
)

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

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
RUN_ID_ANY = "*"
NODE_ANY = "*"

_LOGGER = logging.getLogger(__name__)

_LOG_EXCEPTION = logging.ERROR + 1
_TIMEOUT_MSG = "Timeout reached, abort script."

_SHUTDOWN_MAX_WAIT = 60


ACTION_TRACE_NODE_MAX_LEN = 20  # Max length of a trace node for repeated actions

SCRIPT_BREAKPOINT_HIT = "script_breakpoint_hit"
SCRIPT_DEBUG_CONTINUE_STOP = "script_debug_continue_stop_{}_{}"
SCRIPT_DEBUG_CONTINUE_ALL = "script_debug_continue_all"


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
    except _StopScript as ex:
        trace_element.set_error(ex.__cause__ or ex)
        raise ex
    except Exception as ex:
        trace_element.set_error(ex)
        raise ex
    finally:
        trace_stack_pop(trace_stack_cv)


def make_script_schema(schema, default_script_mode, extra=vol.PREVENT_EXTRA):
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
)


async def async_validate_actions_config(
    hass: HomeAssistant, actions: list[ConfigType]
) -> list[ConfigType]:
    """Validate a list of actions."""
    return await asyncio.gather(
        *[async_validate_action_config(hass, action) for action in actions]
    )


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    action_type = cv.determine_script_action(config)

    if action_type in STATIC_VALIDATION_ACTION_TYPES:
        pass

    elif action_type == cv.SCRIPT_ACTION_DEVICE_AUTOMATION:
        platform = await device_automation.async_get_device_automation_platform(
            hass, config[CONF_DOMAIN], "action"
        )
        config = platform.ACTION_SCHEMA(config)  # type: ignore

    elif action_type == cv.SCRIPT_ACTION_CHECK_CONDITION:
        if config[CONF_CONDITION] == "device":
            platform = await device_automation.async_get_device_automation_platform(
                hass, config[CONF_DOMAIN], "condition"
            )
            config = platform.CONDITION_SCHEMA(config)  # type: ignore

    elif action_type == cv.SCRIPT_ACTION_WAIT_FOR_TRIGGER:
        config[CONF_WAIT_FOR_TRIGGER] = await async_validate_trigger_config(
            hass, config[CONF_WAIT_FOR_TRIGGER]
        )

    elif action_type == cv.SCRIPT_ACTION_REPEAT:
        config[CONF_SEQUENCE] = await async_validate_actions_config(
            hass, config[CONF_REPEAT][CONF_SEQUENCE]
        )

    elif action_type == cv.SCRIPT_ACTION_CHOOSE:
        if CONF_DEFAULT in config:
            config[CONF_DEFAULT] = await async_validate_actions_config(
                hass, config[CONF_DEFAULT]
            )

        for choose_conf in config[CONF_CHOOSE]:
            choose_conf[CONF_SEQUENCE] = await async_validate_actions_config(
                hass, choose_conf[CONF_SEQUENCE]
            )

    else:
        raise ValueError(f"No validation for {action_type}")

    return config


class _StopScript(Exception):
    """Throw if script needs to stop."""


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
        # pylint: disable=protected-access
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

    async def async_run(self) -> None:
        """Run script."""
        try:
            self._log("Running %s", self._script.running_description)
            for self._step, self._action in enumerate(self._script.sequence):
                if self._stop.is_set():
                    script_execution_set("cancelled")
                    break
                await self._async_step(log_exceptions=False)
            else:
                script_execution_set("finished")
        except _StopScript:
            script_execution_set("aborted")
        except Exception:
            script_execution_set("error")
            raise
        finally:
            self._finish()

    async def _async_step(self, log_exceptions):
        with trace_path(str(self._step)):
            async with trace_action(self._hass, self, self._stop, self._variables):
                if self._stop.is_set():
                    return
                try:
                    handler = f"_async_{cv.determine_script_action(self._action)}_step"
                    await getattr(self, handler)()
                except Exception as ex:
                    if not isinstance(ex, _StopScript) and (
                        self._log_exceptions or log_exceptions
                    ):
                        self._log_exception(ex)
                    raise

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
            raise _StopScript from ex

    async def _async_delay_step(self):
        """Handle delay."""
        delay = self._get_pos_time_period_template(CONF_DELAY)

        self._step_log(f"delay {delay}")

        delay = delay.total_seconds()
        self._changed()
        trace_set_result(delay=delay, done=False)
        try:
            async with async_timeout.timeout(delay):
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
            wait_var = self._variables["wait"]
            wait_var["remaining"] = to_context.remaining if to_context else timeout
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
            async with async_timeout.timeout(timeout) as to_context:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError as ex:
            self._variables["wait"]["remaining"] = 0.0
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                trace_set_result(wait=self._variables["wait"], timeout=True)
                raise _StopScript from ex
        finally:
            for task in tasks:
                task.cancel()
            unsub()

    async def _async_run_long_action(self, long_task: asyncio.tasks.Task) -> None:
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
            long_task.result()
        else:
            # Stopped before long task completed, so cancel it.
            await async_cancel_long_task()

    async def _async_call_service_step(self):
        """Call the service specified in the action."""
        self._step_log("call service")

        params = service.async_prepare_call_from_config(
            self._hass, self._action, self._variables
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
            limit = SERVICE_CALL_LIMIT

        trace_set_result(params=params, running_script=running_script, limit=limit)
        service_task = self._hass.async_create_task(
            self._hass.services.async_call(
                **params,
                blocking=True,
                context=self._context,
                limit=limit,
            )
        )
        if limit is not None:
            # There is a call limit, so just wait for it to finish.
            await service_task
            return

        await self._async_run_long_action(service_task)

    async def _async_device_step(self):
        """Perform the device automation specified in the action."""
        self._step_log("device automation")
        platform = await device_automation.async_get_device_automation_platform(
            self._hass, self._action[CONF_DOMAIN], "action"
        )
        await platform.async_call_action_from_config(
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
        for conf in [CONF_EVENT_DATA, CONF_EVENT_DATA_TEMPLATE]:
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
            with trace_path("condition"):
                check = cond(self._hass, self._variables)
        except exceptions.ConditionError as ex:
            _LOGGER.warning("Error in 'condition' evaluation:\n%s", ex)
            check = False

        self._log("Test condition %s: %s", self._script.last_action, check)
        trace_set_result(result=check)
        if not check:
            raise _StopScript

    def _test_conditions(self, conditions, name, condition_path=None):
        if condition_path is None:
            condition_path = name

        @trace_condition_function
        def traced_test_conditions(hass, variables):
            try:
                with trace_path(condition_path):
                    for idx, cond in enumerate(conditions):
                        with trace_path(str(idx)):
                            if not cond(hass, variables):
                                return False
            except exceptions.ConditionError as ex:
                _LOGGER.warning("Error in '%s[%s]' evaluation: %s", name, idx, ex)
                return None

            return True

        result = traced_test_conditions(self._hass, self._variables)
        return result

    @async_trace_path("repeat")
    async def _async_repeat_step(self):
        """Repeat a sequence."""
        description = self._action.get(CONF_ALIAS, "sequence")
        repeat = self._action[CONF_REPEAT]

        saved_repeat_vars = self._variables.get("repeat")

        def set_repeat_var(iteration, count=None):
            repeat_vars = {"first": iteration == 1, "index": iteration}
            if count:
                repeat_vars["last"] = iteration == count
            self._variables["repeat"] = repeat_vars

        # pylint: disable=protected-access
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
                    raise _StopScript from ex
            extra_msg = f" of {count}"
            for iteration in range(1, count + 1):
                set_repeat_var(iteration, count)
                await async_run_sequence(iteration, extra_msg)
                if self._stop.is_set():
                    break

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
            del self._variables["repeat"]

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
            wait_var = self._variables["wait"]
            wait_var["remaining"] = to_context.remaining if to_context else timeout
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
            async with async_timeout.timeout(timeout) as to_context:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError as ex:
            self._variables["wait"]["remaining"] = 0.0
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                trace_set_result(wait=self._variables["wait"], timeout=True)
                raise _StopScript from ex
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
            lock_task.cancel()
            self._finish()
            raise
        finally:
            stop_task.cancel()
        self.lock_acquired = lock_task.done() and not lock_task.cancelled()

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


async def _async_stop_scripts_after_shutdown(hass, point_in_time):
    """Stop running Script objects started after shutdown."""
    running_scripts = [
        script for script in hass.data[DATA_SCRIPTS] if script["instance"].is_running
    ]
    if running_scripts:
        names = ", ".join([script["instance"].name for script in running_scripts])
        _LOGGER.warning("Stopping scripts running too long after shutdown: %s", names)
        await asyncio.gather(
            *[
                script["instance"].async_stop(update_state=False)
                for script in running_scripts
            ]
        )


async def _async_stop_scripts_at_shutdown(hass, event):
    """Stop running Script objects started before shutdown."""
    async_call_later(
        hass, _SHUTDOWN_MAX_WAIT, partial(_async_stop_scripts_after_shutdown, hass)
    )

    running_scripts = [
        script
        for script in hass.data[DATA_SCRIPTS]
        if script["instance"].is_running and script["started_before_shutdown"]
    ]
    if running_scripts:
        names = ", ".join([script["instance"].name for script in running_scripts])
        _LOGGER.debug("Stopping scripts running at shutdown: %s", names)
        await asyncio.gather(
            *[script["instance"].async_stop() for script in running_scripts]
        )


_VarsType = Union[Dict[str, Any], MappingProxyType]


def _referenced_extract_ids(data: dict[str, Any], key: str, found: set[str]) -> None:
    """Extract referenced IDs."""
    if not data:
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
        running_description: str | None = None,
        change_listener: Callable[..., Any] | None = None,
        script_mode: str = DEFAULT_SCRIPT_MODE,
        max_runs: int = DEFAULT_MAX,
        max_exceeded: str = DEFAULT_MAX_EXCEEDED,
        logger: logging.Logger | None = None,
        log_exceptions: bool = True,
        top_level: bool = True,
        variables: ScriptVariables | None = None,
    ) -> None:
        """Initialize the script."""
        all_scripts = hass.data.get(DATA_SCRIPTS)
        if not all_scripts:
            all_scripts = hass.data[DATA_SCRIPTS] = []
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, partial(_async_stop_scripts_at_shutdown, hass)
            )
        self._top_level = top_level
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
        self._referenced_entities: set[str] | None = None
        self._referenced_devices: set[str] | None = None
        self._referenced_areas: set[str] | None = None
        self.variables = variables
        self._variables_dynamic = template.is_complex(variables)
        if self._variables_dynamic:
            template.attach(hass, variables)

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
        for choose_data in self._choose_data.values():
            for _, script in choose_data["choices"]:
                script.update_logger(self._logger)
            if choose_data["default"] is not None:
                choose_data["default"].update_logger(self._logger)

    def _changed(self) -> None:
        if self._change_listener_job:
            self._hass.async_run_hass_job(self._change_listener_job)

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
    def referenced_areas(self):
        """Return a set of referenced areas."""
        if self._referenced_areas is not None:
            return self._referenced_areas

        referenced: set[str] = set()

        for step in self.sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CALL_SERVICE:
                for data in (
                    step.get(CONF_TARGET),
                    step.get(service.CONF_SERVICE_DATA),
                    step.get(service.CONF_SERVICE_DATA_TEMPLATE),
                ):
                    _referenced_extract_ids(data, ATTR_AREA_ID, referenced)

        self._referenced_areas = referenced
        return referenced

    @property
    def referenced_devices(self):
        """Return a set of referenced devices."""
        if self._referenced_devices is not None:
            return self._referenced_devices

        referenced: set[str] = set()

        for step in self.sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CALL_SERVICE:
                for data in (
                    step.get(CONF_TARGET),
                    step.get(service.CONF_SERVICE_DATA),
                    step.get(service.CONF_SERVICE_DATA_TEMPLATE),
                ):
                    _referenced_extract_ids(data, ATTR_DEVICE_ID, referenced)

            elif action == cv.SCRIPT_ACTION_CHECK_CONDITION:
                referenced |= condition.async_extract_devices(step)

            elif action == cv.SCRIPT_ACTION_DEVICE_AUTOMATION:
                referenced.add(step[CONF_DEVICE_ID])

        self._referenced_devices = referenced
        return referenced

    @property
    def referenced_entities(self):
        """Return a set of referenced entities."""
        if self._referenced_entities is not None:
            return self._referenced_entities

        referenced: set[str] = set()

        for step in self.sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CALL_SERVICE:
                for data in (
                    step,
                    step.get(CONF_TARGET),
                    step.get(service.CONF_SERVICE_DATA),
                    step.get(service.CONF_SERVICE_DATA_TEMPLATE),
                ):
                    _referenced_extract_ids(data, ATTR_ENTITY_ID, referenced)

            elif action == cv.SCRIPT_ACTION_CHECK_CONDITION:
                referenced |= condition.async_extract_entities(step)

            elif action == cv.SCRIPT_ACTION_ACTIVATE_SCENE:
                referenced.add(step[CONF_SCENE])

        self._referenced_entities = referenced
        return referenced

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
    ) -> None:
        """Run script."""
        if context is None:
            self._log(
                "Running script requires passing in a context", level=logging.WARNING
            )
            context = Context()

        if self.is_running:
            if self.script_mode == SCRIPT_MODE_SINGLE:
                if self._max_exceeded != "SILENT":
                    self._log("Already running", level=LOGSEVERITY[self._max_exceeded])
                script_execution_set("failed_single")
                return
            if self.script_mode != SCRIPT_MODE_RESTART and self.runs == self.max_runs:
                if self._max_exceeded != "SILENT":
                    self._log(
                        "Maximum number of runs exceeded",
                        level=LOGSEVERITY[self._max_exceeded],
                    )
                script_execution_set("failed_max_runs")
                return

        # If this is a top level Script then make a copy of the variables in case they
        # are read-only, but more importantly, so as not to leak any variables created
        # during the run back to the caller.
        if self._top_level:
            if self.variables:
                try:
                    variables = self.variables.async_render(
                        self._hass,
                        run_variables,
                    )
                except template.TemplateError as err:
                    self._log("Error rendering variables: %s", err, level=logging.ERROR)
                    raise
            elif run_variables:
                variables = dict(run_variables)
            else:
                variables = {}

            variables["context"] = context
        else:
            variables = cast(dict, run_variables)

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
            await asyncio.shield(run.async_run())
        except asyncio.CancelledError:
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
        # Collect a a list of script runs to stop. This must be done before calling
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
        cond = self._config_cache.get(config_cache_key)
        if not cond:
            cond = await condition.async_from_config(self._hass, config, False)
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
        sub_script = self._repeat_script.get(step)
        if not sub_script:
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
        choose_data = self._choose_data.get(step)
        if not choose_data:
            choose_data = await self._async_prep_choose_data(step)
            self._choose_data[step] = choose_data
        return choose_data

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
