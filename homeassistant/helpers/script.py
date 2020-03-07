"""Helpers to execute scripts."""
from abc import ABC, abstractmethod
import asyncio
from contextlib import suppress
from datetime import datetime
from itertools import islice
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, cast

import voluptuous as vol

from homeassistant import exceptions
import homeassistant.components.device_automation as device_automation
import homeassistant.components.scene as scene
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CONDITION,
    CONF_CONTINUE_ON_TIMEOUT,
    CONF_DELAY,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_EVENT_DATA,
    CONF_EVENT_DATA_TEMPLATE,
    CONF_SCENE,
    CONF_TIMEOUT,
    CONF_WAIT_TEMPLATE,
    SERVICE_TURN_ON,
)
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    service,
    template as template,
)
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_template,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import utcnow

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

CONF_ALIAS = "alias"

IF_RUNNING_ERROR = "error"
IF_RUNNING_IGNORE = "ignore"
IF_RUNNING_PARALLEL = "parallel"
IF_RUNNING_RESTART = "restart"
# First choice is default
IF_RUNNING_CHOICES = [
    IF_RUNNING_PARALLEL,
    IF_RUNNING_ERROR,
    IF_RUNNING_IGNORE,
    IF_RUNNING_RESTART,
]

RUN_MODE_BACKGROUND = "background"
RUN_MODE_BLOCKING = "blocking"
RUN_MODE_LEGACY = "legacy"
# First choice is default
RUN_MODE_CHOICES = [
    RUN_MODE_BLOCKING,
    RUN_MODE_BACKGROUND,
    RUN_MODE_LEGACY,
]

_LOG_EXCEPTION = logging.ERROR + 1
_TIMEOUT_MSG = "Timeout reached, abort script."


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
    if (
        action_type == cv.SCRIPT_ACTION_CHECK_CONDITION
        and config[CONF_CONDITION] == "device"
    ):
        platform = await device_automation.async_get_device_automation_platform(
            hass, config[CONF_DOMAIN], "condition"
        )
        config = platform.CONDITION_SCHEMA(config)  # type: ignore

    return config


class _StopScript(Exception):
    """Throw if script needs to stop."""


class _SuspendScript(Exception):
    """Throw if script needs to suspend."""


class _ScriptRunBase(ABC):
    """Common data & methods for managing Script sequence run."""

    def __init__(
        self,
        hass: HomeAssistant,
        script: "Script",
        variables: Optional[Sequence],
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

    def _changed(self):
        self._script._changed()  # pylint: disable=protected-access

    @property
    def _config_cache(self):
        return self._script._config_cache  # pylint: disable=protected-access

    @abstractmethod
    async def async_run(self) -> None:
        """Run script."""

    async def _async_step(self, log_exceptions):
        try:
            await getattr(
                self, f"_async_{cv.determine_script_action(self._action)}_step"
            )()
        except Exception as err:
            if not isinstance(err, (_SuspendScript, _StopScript)) and (
                self._log_exceptions or log_exceptions
            ):
                self._log_exception(err)
            raise

    @abstractmethod
    async def async_stop(self) -> None:
        """Stop script run."""

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

    @abstractmethod
    async def _async_delay_step(self):
        """Handle delay."""

    def _prep_delay_step(self):
        try:
            delay = vol.All(cv.time_period, cv.positive_timedelta)(
                template.render_complex(self._action[CONF_DELAY], self._variables)
            )
        except (exceptions.TemplateError, vol.Invalid) as ex:
            self._raise(
                "Error rendering %s delay template: %s",
                self._script.name,
                ex,
                exception=_StopScript,
            )

        self._script.last_action = self._action.get(CONF_ALIAS, f"delay {delay}")
        self._log("Executing step %s", self._script.last_action)

        return delay

    @abstractmethod
    async def _async_wait_template_step(self):
        """Handle a wait template."""

    def _prep_wait_template_step(self, async_script_wait):
        wait_template = self._action[CONF_WAIT_TEMPLATE]
        wait_template.hass = self._hass

        self._script.last_action = self._action.get(CONF_ALIAS, "wait template")
        self._log("Executing step %s", self._script.last_action)

        # check if condition already okay
        if condition.async_template(self._hass, wait_template, self._variables):
            return None

        return async_track_template(
            self._hass, wait_template, async_script_wait, self._variables
        )

    async def _async_call_service_step(self):
        """Call the service specified in the action."""
        self._script.last_action = self._action.get(CONF_ALIAS, "call service")
        self._log("Executing step %s", self._script.last_action)
        await service.async_call_from_config(
            self._hass,
            self._action,
            blocking=True,
            variables=self._variables,
            validate_config=False,
            context=self._context,
        )

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
        event_data = dict(self._action.get(CONF_EVENT_DATA, {}))
        if CONF_EVENT_DATA_TEMPLATE in self._action:
            try:
                event_data.update(
                    template.render_complex(
                        self._action[CONF_EVENT_DATA_TEMPLATE], self._variables
                    )
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
        config_cache_key = frozenset((k, str(v)) for k, v in self._action.items())
        config = self._config_cache.get(config_cache_key)
        if not config:
            config = await condition.async_from_config(self._hass, self._action, False)
            self._config_cache[config_cache_key] = config

        self._script.last_action = self._action.get(
            CONF_ALIAS, self._action[CONF_CONDITION]
        )
        check = config(self._hass, self._variables)
        self._log("Test condition %s: %s", self._script.last_action, check)
        if not check:
            raise _StopScript

    def _log(self, msg, *args, level=logging.INFO):
        self._script._log(msg, *args, level=level)  # pylint: disable=protected-access

    def _raise(self, msg, *args, exception=None):
        # pylint: disable=protected-access
        self._script._raise(msg, *args, exception=exception)


class _ScriptRun(_ScriptRunBase):
    """Manage Script sequence run."""

    def __init__(
        self,
        hass: HomeAssistant,
        script: "Script",
        variables: Optional[Sequence],
        context: Optional[Context],
        log_exceptions: bool,
    ) -> None:
        super().__init__(hass, script, variables, context, log_exceptions)
        self._stop = asyncio.Event()
        self._stopped = asyncio.Event()

    async def _async_run(self, propagate_exceptions=True):
        self._log("Running script")
        try:
            for self._step, self._action in enumerate(self._script.sequence):
                if self._stop.is_set():
                    break
                await self._async_step(not propagate_exceptions)
        except _StopScript:
            pass
        except Exception:  # pylint: disable=broad-except
            if propagate_exceptions:
                raise
        finally:
            if not self._stop.is_set():
                self._changed()
            self._script.last_action = None
            self._script._runs.remove(self)  # pylint: disable=protected-access
            self._stopped.set()

    async def async_stop(self) -> None:
        """Stop script run."""
        self._stop.set()
        await self._stopped.wait()

    async def _async_delay_step(self):
        """Handle delay."""
        timeout = self._prep_delay_step().total_seconds()
        if not self._stop.is_set():
            self._changed()
        await asyncio.wait({self._stop.wait()}, timeout=timeout)

    async def _async_wait_template_step(self):
        """Handle a wait template."""

        @callback
        def async_script_wait(entity_id, from_s, to_s):
            """Handle script after template condition is true."""
            done.set()

        unsub = self._prep_wait_template_step(async_script_wait)
        if not unsub:
            return

        if not self._stop.is_set():
            self._changed()
        try:
            timeout = self._action[CONF_TIMEOUT].total_seconds()
        except KeyError:
            timeout = None
        done = asyncio.Event()
        try:
            await asyncio.wait_for(
                asyncio.wait(
                    {self._stop.wait(), done.wait()},
                    return_when=asyncio.FIRST_COMPLETED,
                ),
                timeout,
            )
        except asyncio.TimeoutError:
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                raise _StopScript
        finally:
            unsub()


class _BackgroundScriptRun(_ScriptRun):
    """Manage background Script sequence run."""

    async def async_run(self) -> None:
        """Run script."""
        self._hass.async_create_task(self._async_run(False))


class _BlockingScriptRun(_ScriptRun):
    """Manage blocking Script sequence run."""

    async def async_run(self) -> None:
        """Run script."""
        try:
            await asyncio.shield(self._async_run())
        except asyncio.CancelledError:
            await self.async_stop()
            raise


class _LegacyScriptRun(_ScriptRunBase):
    """Manage legacy Script sequence run."""

    def __init__(
        self,
        hass: HomeAssistant,
        script: "Script",
        variables: Optional[Sequence],
        context: Optional[Context],
        log_exceptions: bool,
        shared: Optional["_LegacyScriptRun"],
    ) -> None:
        super().__init__(hass, script, variables, context, log_exceptions)
        if shared:
            self._shared = shared
        else:
            # To implement legacy behavior we need to share the following "run state"
            # amongst all runs, so it will only exist in the first instantiation of
            # concurrent runs, and the rest will use it, too.
            self._current = -1
            self._async_listeners: List[CALLBACK_TYPE] = []
            self._shared = self

    @property
    def _cur(self):
        return self._shared._current  # pylint: disable=protected-access

    @_cur.setter
    def _cur(self, value):
        self._shared._current = value  # pylint: disable=protected-access

    @property
    def _async_listener(self):
        return self._shared._async_listeners  # pylint: disable=protected-access

    async def async_run(self) -> None:
        """Run script."""
        await self._async_run()

    async def _async_run(self, propagate_exceptions=True):
        if self._cur == -1:
            self._log("Running script")
            self._cur = 0

        # Unregister callback if we were in a delay or wait but turn on is
        # called again. In that case we just continue execution.
        self._async_remove_listener()

        suspended = False
        try:
            for self._step, self._action in islice(
                enumerate(self._script.sequence), self._cur, None
            ):
                await self._async_step(not propagate_exceptions)
        except _StopScript:
            pass
        except _SuspendScript:
            # Store next step to take and notify change listeners
            self._cur = self._step + 1
            suspended = True
            return
        except Exception:  # pylint: disable=broad-except
            if propagate_exceptions:
                raise
        finally:
            if self._cur != -1:
                self._changed()
            if not suspended:
                self._script.last_action = None
                await self.async_stop()

    async def async_stop(self) -> None:
        """Stop script run."""
        if self._cur == -1:
            return

        self._cur = -1
        self._async_remove_listener()
        self._script._runs.clear()  # pylint: disable=protected-access

    async def _async_delay_step(self):
        """Handle delay."""
        delay = self._prep_delay_step()

        @callback
        def async_script_delay(now):
            """Handle delay."""
            with suppress(ValueError):
                self._async_listener.remove(unsub)
            self._hass.async_create_task(self._async_run(False))

        unsub = async_track_point_in_utc_time(
            self._hass, async_script_delay, utcnow() + delay
        )
        self._async_listener.append(unsub)
        raise _SuspendScript

    async def _async_wait_template_step(self):
        """Handle a wait template."""

        @callback
        def async_script_wait(entity_id, from_s, to_s):
            """Handle script after template condition is true."""
            self._async_remove_listener()
            self._hass.async_create_task(self._async_run(False))

        @callback
        def async_script_timeout(now):
            """Call after timeout is retrieve."""
            with suppress(ValueError):
                self._async_listener.remove(unsub)

            # Check if we want to continue to execute
            # the script after the timeout
            if self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._hass.async_create_task(self._async_run(False))
            else:
                self._log(_TIMEOUT_MSG)
                self._hass.async_create_task(self.async_stop())

        unsub_wait = self._prep_wait_template_step(async_script_wait)
        if not unsub_wait:
            return
        self._async_listener.append(unsub_wait)

        if CONF_TIMEOUT in self._action:
            unsub = async_track_point_in_utc_time(
                self._hass, async_script_timeout, utcnow() + self._action[CONF_TIMEOUT]
            )
            self._async_listener.append(unsub)

        raise _SuspendScript

    def _async_remove_listener(self):
        """Remove listeners, if any."""
        for unsub in self._async_listener:
            unsub()
        self._async_listener.clear()


class Script:
    """Representation of a script."""

    def __init__(
        self,
        hass: HomeAssistant,
        sequence: Sequence[Dict[str, Any]],
        name: Optional[str] = None,
        change_listener: Optional[Callable[..., Any]] = None,
        if_running: Optional[str] = None,
        run_mode: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        log_exceptions: bool = True,
    ) -> None:
        """Initialize the script."""
        self._logger = logger or logging.getLogger(__name__)
        self._hass = hass
        self.sequence = sequence
        template.attach(hass, self.sequence)
        self.name = name
        self._change_listener = change_listener
        self.last_action = None
        self.last_triggered: Optional[datetime] = None
        self.can_cancel = any(
            CONF_DELAY in action or CONF_WAIT_TEMPLATE in action
            for action in self.sequence
        )
        if not if_running and not run_mode:
            self._if_running = IF_RUNNING_PARALLEL
            self._run_mode = RUN_MODE_LEGACY
        elif if_running and run_mode == RUN_MODE_LEGACY:
            self._raise('Cannot use if_running if run_mode is "legacy"')
        else:
            self._if_running = if_running or IF_RUNNING_CHOICES[0]
            self._run_mode = run_mode or RUN_MODE_CHOICES[0]
        self._runs: List[_ScriptRunBase] = []
        self._log_exceptions = log_exceptions
        self._config_cache: Dict[Set[Tuple], Callable[..., bool]] = {}
        self._referenced_entities: Optional[Set[str]] = None
        self._referenced_devices: Optional[Set[str]] = None

    def _changed(self):
        if self._change_listener:
            self._hass.async_add_job(self._change_listener)

    @property
    def is_running(self) -> bool:
        """Return true if script is on."""
        return len(self._runs) > 0

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
                data = step.get(service.CONF_SERVICE_DATA)
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

    def run(self, variables=None, context=None):
        """Run script."""
        asyncio.run_coroutine_threadsafe(
            self.async_run(variables, context), self._hass.loop
        ).result()

    async def async_run(
        self, variables: Optional[Sequence] = None, context: Optional[Context] = None
    ) -> None:
        """Run script."""
        if self.is_running:
            if self._if_running == IF_RUNNING_IGNORE:
                self._log("Skipping script")
                return

            if self._if_running == IF_RUNNING_ERROR:
                self._raise("Already running")
            if self._if_running == IF_RUNNING_RESTART:
                self._log("Restarting script")
                await self.async_stop()

        self.last_triggered = utcnow()
        if self._run_mode == RUN_MODE_LEGACY:
            if self._runs:
                shared = cast(Optional[_LegacyScriptRun], self._runs[0])
            else:
                shared = None
            run: _ScriptRunBase = _LegacyScriptRun(
                self._hass, self, variables, context, self._log_exceptions, shared
            )
        else:
            if self._run_mode == RUN_MODE_BACKGROUND:
                run = _BackgroundScriptRun(
                    self._hass, self, variables, context, self._log_exceptions
                )
            else:
                run = _BlockingScriptRun(
                    self._hass, self, variables, context, self._log_exceptions
                )
        self._runs.append(run)
        await run.async_run()

    async def async_stop(self) -> None:
        """Stop running script."""
        if not self.is_running:
            return
        await asyncio.shield(asyncio.gather(*(run.async_stop() for run in self._runs)))
        self._changed()

    def _log(self, msg, *args, level=logging.INFO):
        if self.name:
            msg = f"{self.name}: {msg}"
        if level == _LOG_EXCEPTION:
            self._logger.exception(msg, *args)
        else:
            self._logger.log(level, msg, *args)

    def _raise(self, msg, *args, exception=None):
        if not exception:
            exception = exceptions.HomeAssistantError
        self._log(msg, *args, level=logging.ERROR)
        raise exception(msg % args)
