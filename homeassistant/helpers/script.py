"""Helpers to execute scripts."""
import asyncio
from datetime import datetime, timedelta
from functools import partial
import itertools
import logging
from types import MappingProxyType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
    cast,
)

from async_timeout import timeout
import voluptuous as vol

from homeassistant import exceptions
import homeassistant.components.device_automation as device_automation
from homeassistant.components.logger import LOGSEVERITY
import homeassistant.components.scene as scene
from homeassistant.const import (
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
    CONF_TIMEOUT,
    CONF_UNTIL,
    CONF_WAIT_FOR_TRIGGER,
    CONF_WAIT_TEMPLATE,
    CONF_WHILE,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_TURN_ON,
)
from homeassistant.core import SERVICE_CALL_LIMIT, Context, HomeAssistant, callback
from homeassistant.helpers import condition, config_validation as cv, template
from homeassistant.helpers.event import async_call_later, async_track_template
from homeassistant.helpers.script_variables import ScriptVariables
from homeassistant.helpers.service import (
    CONF_SERVICE_DATA,
    async_prepare_call_from_config,
)
from homeassistant.helpers.trigger import (
    async_initialize_triggers,
    async_validate_trigger_config,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

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
ATTR_MODE = "mode"

DATA_SCRIPTS = "helpers.script"

_LOGGER = logging.getLogger(__name__)

_LOG_EXCEPTION = logging.ERROR + 1
_TIMEOUT_MSG = "Timeout reached, abort script."

_SHUTDOWN_MAX_WAIT = 60


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


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    action_type = cv.determine_script_action(config)

    if action_type == cv.SCRIPT_ACTION_DEVICE_AUTOMATION:
        platform = await device_automation.async_get_device_automation_platform(
            hass, config[CONF_DOMAIN], "action"
        )
        config = platform.ACTION_SCHEMA(config)  # type: ignore
    elif (
        action_type == cv.SCRIPT_ACTION_CHECK_CONDITION
        and config[CONF_CONDITION] == "device"
    ):
        platform = await device_automation.async_get_device_automation_platform(
            hass, config[CONF_DOMAIN], "condition"
        )
        config = platform.CONDITION_SCHEMA(config)  # type: ignore
    elif action_type == cv.SCRIPT_ACTION_WAIT_FOR_TRIGGER:
        config[CONF_WAIT_FOR_TRIGGER] = await async_validate_trigger_config(
            hass, config[CONF_WAIT_FOR_TRIGGER]
        )

    return config


class _StopScript(Exception):
    """Throw if script needs to stop."""


class _ScriptRun:
    """Manage Script sequence run."""

    def __init__(
        self,
        hass: HomeAssistant,
        script: "Script",
        variables: Dict[str, Any],
        context: Optional[Context],
        log_exceptions: bool,
    ) -> None:
        self._hass = hass
        self._script = script
        self._variables = variables
        self._context = context
        self._log_exceptions = log_exceptions
        self._step = -1
        self._action: Optional[Dict[str, Any]] = None
        self._stop = asyncio.Event()
        self._stopped = asyncio.Event()

    def _changed(self):
        if not self._stop.is_set():
            self._script._changed()  # pylint: disable=protected-access

    async def _async_get_condition(self, config):
        # pylint: disable=protected-access
        return await self._script._async_get_condition(config)

    def _log(self, msg, *args, level=logging.INFO):
        self._script._log(msg, *args, level=level)  # pylint: disable=protected-access

    async def async_run(self) -> None:
        """Run script."""
        try:
            if self._stop.is_set():
                return
            self._log("Running %s", self._script.running_description)
            for self._step, self._action in enumerate(self._script.sequence):
                if self._stop.is_set():
                    break
                await self._async_step(log_exceptions=False)
        except _StopScript:
            pass
        finally:
            self._finish()

    async def _async_step(self, log_exceptions):
        try:
            await getattr(
                self, f"_async_{cv.determine_script_action(self._action)}_step"
            )()
        except Exception as ex:
            if not isinstance(ex, (_StopScript, asyncio.CancelledError)) and (
                self._log_exceptions or log_exceptions
            ):
                self._log_exception(ex)
            raise

    def _finish(self):
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

        self._script.last_action = self._action.get(CONF_ALIAS, f"delay {delay}")
        self._log("Executing step %s", self._script.last_action)

        delay = delay.total_seconds()
        self._changed()
        try:
            async with timeout(delay):
                await self._stop.wait()
        except asyncio.TimeoutError:
            pass

    async def _async_wait_template_step(self):
        """Handle a wait template."""
        if CONF_TIMEOUT in self._action:
            delay = self._get_pos_time_period_template(CONF_TIMEOUT).total_seconds()
        else:
            delay = None

        self._script.last_action = self._action.get(CONF_ALIAS, "wait template")
        self._log(
            "Executing step %s%s",
            self._script.last_action,
            "" if delay is None else f" (timeout: {timedelta(seconds=delay)})",
        )

        self._variables["wait"] = {"remaining": delay, "completed": False}

        wait_template = self._action[CONF_WAIT_TEMPLATE]
        wait_template.hass = self._hass

        # check if condition already okay
        if condition.async_template(self._hass, wait_template, self._variables):
            self._variables["wait"]["completed"] = True
            return

        @callback
        def async_script_wait(entity_id, from_s, to_s):
            """Handle script after template condition is true."""
            self._variables["wait"] = {
                "remaining": to_context.remaining if to_context else delay,
                "completed": True,
            }
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
            async with timeout(delay) as to_context:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError as ex:
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                raise _StopScript from ex
            self._variables["wait"]["remaining"] = 0.0
        finally:
            for task in tasks:
                task.cancel()
            unsub()

    async def _async_run_long_action(self, long_task):
        """Run a long task while monitoring for stop request."""

        async def async_cancel_long_task():
            # Stop long task and wait for it to finish.
            long_task.cancel()
            try:
                await long_task
            except Exception:  # pylint: disable=broad-except
                pass

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
        self._script.last_action = self._action.get(CONF_ALIAS, "call service")
        self._log("Executing step %s", self._script.last_action)

        domain, service, service_data = async_prepare_call_from_config(
            self._hass, self._action, self._variables
        )

        running_script = (
            domain == "automation"
            and service == "trigger"
            or domain in ("python_script", "script")
        )
        # If this might start a script then disable the call timeout.
        # Otherwise use the normal service call limit.
        if running_script:
            limit = None
        else:
            limit = SERVICE_CALL_LIMIT

        service_task = self._hass.async_create_task(
            self._hass.services.async_call(
                domain,
                service,
                service_data,
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
        self._script.last_action = self._action.get(CONF_ALIAS, "device automation")
        self._log("Executing step %s", self._script.last_action)
        platform = await device_automation.async_get_device_automation_platform(
            self._hass, self._action[CONF_DOMAIN], "action"
        )
        await platform.async_call_action_from_config(
            self._hass, self._action, self._variables, self._context
        )

    async def _async_scene_step(self):
        """Activate the scene specified in the action."""
        self._script.last_action = self._action.get(CONF_ALIAS, "activate scene")
        self._log("Executing step %s", self._script.last_action)
        await self._hass.services.async_call(
            scene.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: self._action[CONF_SCENE]},
            blocking=True,
            context=self._context,
        )

    async def _async_event_step(self):
        """Fire an event."""
        self._script.last_action = self._action.get(
            CONF_ALIAS, self._action[CONF_EVENT]
        )
        self._log("Executing step %s", self._script.last_action)
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

        self._hass.bus.async_fire(
            self._action[CONF_EVENT], event_data, context=self._context
        )

    async def _async_condition_step(self):
        """Test if condition is matching."""
        self._script.last_action = self._action.get(
            CONF_ALIAS, self._action[CONF_CONDITION]
        )
        cond = await self._async_get_condition(self._action)
        check = cond(self._hass, self._variables)
        self._log("Test condition %s: %s", self._script.last_action, check)
        if not check:
            raise _StopScript

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
                if self._stop.is_set() or not all(
                    cond(self._hass, self._variables) for cond in conditions
                ):
                    break
                await async_run_sequence(iteration)

        elif CONF_UNTIL in repeat:
            conditions = [
                await self._async_get_condition(config) for config in repeat[CONF_UNTIL]
            ]
            for iteration in itertools.count(1):
                set_repeat_var(iteration)
                await async_run_sequence(iteration)
                if self._stop.is_set() or all(
                    cond(self._hass, self._variables) for cond in conditions
                ):
                    break

        if saved_repeat_vars:
            self._variables["repeat"] = saved_repeat_vars
        else:
            del self._variables["repeat"]

    async def _async_choose_step(self):
        """Choose a sequence."""
        # pylint: disable=protected-access
        choose_data = await self._script._async_get_choose_data(self._step)

        for conditions, script in choose_data["choices"]:
            if all(condition(self._hass, self._variables) for condition in conditions):
                await self._async_run_script(script)
                return

        if choose_data["default"]:
            await self._async_run_script(choose_data["default"])

    async def _async_wait_for_trigger_step(self):
        """Wait for a trigger event."""
        if CONF_TIMEOUT in self._action:
            delay = self._get_pos_time_period_template(CONF_TIMEOUT).total_seconds()
        else:
            delay = None

        self._script.last_action = self._action.get(CONF_ALIAS, "wait for trigger")
        self._log(
            "Executing step %s%s",
            self._script.last_action,
            "" if delay is None else f" (timeout: {timedelta(seconds=delay)})",
        )

        variables = {**self._variables}
        self._variables["wait"] = {"remaining": delay, "trigger": None}

        async def async_done(variables, context=None):
            self._variables["wait"] = {
                "remaining": to_context.remaining if to_context else delay,
                "trigger": variables["trigger"],
            }
            done.set()

        def log_cb(level, msg):
            self._log(msg, level=level)

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
        done = asyncio.Event()
        tasks = [
            self._hass.async_create_task(flag.wait()) for flag in (self._stop, done)
        ]
        try:
            async with timeout(delay) as to_context:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.TimeoutError as ex:
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                raise _StopScript from ex
            self._variables["wait"]["remaining"] = 0.0
        finally:
            for task in tasks:
                task.cancel()
            remove_triggers()

    async def _async_run_script(self, script):
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

    def _finish(self):
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


class Script:
    """Representation of a script."""

    def __init__(
        self,
        hass: HomeAssistant,
        sequence: Sequence[Dict[str, Any]],
        name: str,
        domain: str,
        *,
        # Used in "Running <running_description>" log message
        running_description: Optional[str] = None,
        change_listener: Optional[Callable[..., Any]] = None,
        script_mode: str = DEFAULT_SCRIPT_MODE,
        max_runs: int = DEFAULT_MAX,
        max_exceeded: str = DEFAULT_MAX_EXCEEDED,
        logger: Optional[logging.Logger] = None,
        log_exceptions: bool = True,
        top_level: bool = True,
        variables: Optional[ScriptVariables] = None,
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

        self._hass = hass
        self.sequence = sequence
        template.attach(hass, self.sequence)
        self.name = name
        self.domain = domain
        self.running_description = running_description or f"{domain} script"
        self.change_listener = change_listener
        self.script_mode = script_mode
        self._set_logger(logger)
        self._log_exceptions = log_exceptions

        self.last_action = None
        self.last_triggered: Optional[datetime] = None

        self._runs: List[_ScriptRun] = []
        self.max_runs = max_runs
        self._max_exceeded = max_exceeded
        if script_mode == SCRIPT_MODE_QUEUED:
            self._queue_lck = asyncio.Lock()
        self._config_cache: Dict[Set[Tuple], Callable[..., bool]] = {}
        self._repeat_script: Dict[int, Script] = {}
        self._choose_data: Dict[int, Dict[str, Any]] = {}
        self._referenced_entities: Optional[Set[str]] = None
        self._referenced_devices: Optional[Set[str]] = None
        self.variables = variables
        self._variables_dynamic = template.is_complex(variables)
        if self._variables_dynamic:
            template.attach(hass, variables)

    def _set_logger(self, logger: Optional[logging.Logger] = None) -> None:
        if logger:
            self._logger = logger
        else:
            self._logger = logging.getLogger(f"{__name__}.{slugify(self.name)}")

    def update_logger(self, logger: Optional[logging.Logger] = None) -> None:
        """Update logger."""
        self._set_logger(logger)
        for script in self._repeat_script.values():
            script.update_logger(self._logger)
        for choose_data in self._choose_data.values():
            for _, script in choose_data["choices"]:
                script.update_logger(self._logger)
            if choose_data["default"]:
                choose_data["default"].update_logger(self._logger)

    def _changed(self):
        if self.change_listener:
            self._hass.async_run_job(self.change_listener)

    def _chain_change_listener(self, sub_script):
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
    def referenced_devices(self):
        """Return a set of referenced devices."""
        if self._referenced_devices is not None:
            return self._referenced_devices

        referenced = set()

        for step in self.sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CHECK_CONDITION:
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

        referenced = set()

        for step in self.sequence:
            action = cv.determine_script_action(step)

            if action == cv.SCRIPT_ACTION_CALL_SERVICE:
                data = step.get(CONF_SERVICE_DATA)
                if not data:
                    continue

                entity_ids = data.get(ATTR_ENTITY_ID)

                if entity_ids is None:
                    continue

                if isinstance(entity_ids, str):
                    entity_ids = [entity_ids]

                for entity_id in entity_ids:
                    referenced.add(entity_id)

            elif action == cv.SCRIPT_ACTION_CHECK_CONDITION:
                referenced |= condition.async_extract_entities(step)

            elif action == cv.SCRIPT_ACTION_ACTIVATE_SCENE:
                referenced.add(step[CONF_SCENE])

        self._referenced_entities = referenced
        return referenced

    def run(
        self, variables: Optional[_VarsType] = None, context: Optional[Context] = None
    ) -> None:
        """Run script."""
        asyncio.run_coroutine_threadsafe(
            self.async_run(variables, context), self._hass.loop
        ).result()

    async def async_run(
        self,
        run_variables: Optional[_VarsType] = None,
        context: Optional[Context] = None,
        started_action: Optional[Callable[..., Any]] = None,
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
                return
            if self.script_mode == SCRIPT_MODE_RESTART:
                self._log("Restarting")
                await self.async_stop(update_state=False)
            elif len(self._runs) == self.max_runs:
                if self._max_exceeded != "SILENT":
                    self._log(
                        "Maximum number of runs exceeded",
                        level=LOGSEVERITY[self._max_exceeded],
                    )
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

    async def _async_stop(self, update_state):
        aws = [run.async_stop() for run in self._runs]
        if not aws:
            return
        await asyncio.wait(aws)
        if update_state:
            self._changed()

    async def async_stop(self, update_state: bool = True) -> None:
        """Stop running script."""
        await asyncio.shield(self._async_stop(update_state))

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

    def _prep_repeat_script(self, step):
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

    def _get_repeat_script(self, step):
        sub_script = self._repeat_script.get(step)
        if not sub_script:
            sub_script = self._prep_repeat_script(step)
            self._repeat_script[step] = sub_script
        return sub_script

    async def _async_prep_choose_data(self, step):
        action = self.sequence[step]
        step_name = action.get(CONF_ALIAS, f"Choose at step {step+1}")
        choices = []
        for idx, choice in enumerate(action[CONF_CHOOSE], start=1):
            conditions = [
                await self._async_get_condition(config)
                for config in choice.get(CONF_CONDITIONS, [])
            ]
            sub_script = Script(
                self._hass,
                choice[CONF_SEQUENCE],
                f"{self.name}: {step_name}: choice {idx}",
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

    async def _async_get_choose_data(self, step):
        choose_data = self._choose_data.get(step)
        if not choose_data:
            choose_data = await self._async_prep_choose_data(step)
            self._choose_data[step] = choose_data
        return choose_data

    def _log(self, msg, *args, level=logging.INFO):
        msg = f"%s: {msg}"
        args = [self.name, *args]

        if level == _LOG_EXCEPTION:
            self._logger.exception(msg, *args)
        else:
            self._logger.log(level, msg, *args)
