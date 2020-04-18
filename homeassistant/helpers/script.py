"""Helpers to execute scripts."""
from abc import ABC, abstractmethod
import asyncio
from contextlib import suppress
from datetime import datetime
from itertools import islice
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, cast

from async_timeout import timeout
import voluptuous as vol

from homeassistant import exceptions
import homeassistant.components.device_automation as device_automation
import homeassistant.components.scene as scene
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ALIAS,
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
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    SERVICE_CALL_LIMIT,
    Context,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    template as template,
)
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_template,
)
from homeassistant.helpers.service import (
    CONF_SERVICE_DATA,
    async_prepare_call_from_config,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

SCRIPT_MODE_ERROR = "error"
SCRIPT_MODE_IGNORE = "ignore"
SCRIPT_MODE_LEGACY = "legacy"
SCRIPT_MODE_PARALLEL = "parallel"
SCRIPT_MODE_QUEUE = "queue"
SCRIPT_MODE_RESTART = "restart"
SCRIPT_MODE_CHOICES = [
    SCRIPT_MODE_ERROR,
    SCRIPT_MODE_IGNORE,
    SCRIPT_MODE_LEGACY,
    SCRIPT_MODE_PARALLEL,
    SCRIPT_MODE_QUEUE,
    SCRIPT_MODE_RESTART,
]
DEFAULT_SCRIPT_MODE = SCRIPT_MODE_LEGACY

DEFAULT_QUEUE_MAX = 10

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


class AlreadyRunning(exceptions.HomeAssistantError):
    """Throw if script already running and user wants error."""


class QueueFull(exceptions.HomeAssistantError):
    """Throw if script already running, user wants new run queued, but queue is full."""


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
        except Exception as ex:
            if not isinstance(
                ex, (_SuspendScript, _StopScript, asyncio.CancelledError)
            ) and (self._log_exceptions or log_exceptions):
                self._log_exception(ex)
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

        elif isinstance(exception, AlreadyRunning):
            error_desc = "Already running"

        elif isinstance(exception, QueueFull):
            error_desc = "Run queue is full"

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
            self._log(
                "Error rendering %s delay template: %s",
                self._script.name,
                ex,
                level=logging.ERROR,
            )
            raise _StopScript

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

    @abstractmethod
    async def _async_call_service_step(self):
        """Call the service specified in the action."""

    def _prep_call_service_step(self):
        self._script.last_action = self._action.get(CONF_ALIAS, "call service")
        self._log("Executing step %s", self._script.last_action)
        return async_prepare_call_from_config(self._hass, self._action, self._variables)

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

    def _changed(self):
        if not self._stop.is_set():
            super()._changed()

    async def async_run(self) -> None:
        """Run script."""
        try:
            if self._stop.is_set():
                return
            self._script.last_triggered = utcnow()
            self._changed()
            self._log("Running script")
            for self._step, self._action in enumerate(self._script.sequence):
                if self._stop.is_set():
                    break
                await self._async_step(log_exceptions=False)
        except _StopScript:
            pass
        finally:
            self._finish()

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

    async def _async_delay_step(self):
        """Handle delay."""
        delay = self._prep_delay_step().total_seconds()
        self._changed()
        try:
            async with timeout(delay):
                await self._stop.wait()
        except asyncio.TimeoutError:
            pass

    async def _async_wait_template_step(self):
        """Handle a wait template."""

        @callback
        def async_script_wait(entity_id, from_s, to_s):
            """Handle script after template condition is true."""
            done.set()

        unsub = self._prep_wait_template_step(async_script_wait)
        if not unsub:
            return

        self._changed()
        try:
            delay = self._action[CONF_TIMEOUT].total_seconds()
        except KeyError:
            delay = None
        done = asyncio.Event()
        try:
            async with timeout(delay):
                _, pending = await asyncio.wait(
                    {self._stop.wait(), done.wait()},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            for pending_task in pending:
                pending_task.cancel()
        except asyncio.TimeoutError:
            if not self._action.get(CONF_CONTINUE_ON_TIMEOUT, True):
                self._log(_TIMEOUT_MSG)
                raise _StopScript
        finally:
            unsub()

    async def _async_call_service_step(self):
        """Call the service specified in the action."""
        domain, service, service_data = self._prep_call_service_step()

        # If this might start a script then disable the call timeout.
        # Otherwise use the normal service call limit.
        if domain == "script" and service != SERVICE_TURN_OFF:
            limit = None
        else:
            limit = SERVICE_CALL_LIMIT

        coro = self._hass.services.async_call(
            domain,
            service,
            service_data,
            blocking=True,
            context=self._context,
            limit=limit,
        )

        if limit is not None:
            # There is a call limit, so just wait for it to finish.
            await coro
            return

        # No call limit (i.e., potentially starting one or more fully blocking scripts)
        # so watch for a stop request.
        done, pending = await asyncio.wait(
            {self._stop.wait(), coro}, return_when=asyncio.FIRST_COMPLETED,
        )
        # Note that cancelling the service call, if it has not yet returned, will also
        # stop any non-background script runs that it may have started.
        for pending_task in pending:
            pending_task.cancel()
        # Propagate any exceptions that might have happened.
        for done_task in done:
            done_task.result()


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
        done, pending = await asyncio.wait(
            {self._stop.wait(), lock_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for pending_task in pending:
            pending_task.cancel()
        self.lock_acquired = lock_task in done

        # If we've been told to stop, then just finish up. Otherwise, we've acquired the
        # lock so we can go ahead and start the run.
        if self._stop.is_set():
            self._finish()
        else:
            await super().async_run()

    def _finish(self):
        # pylint: disable=protected-access
        self._script._queue_len -= 1
        if self.lock_acquired:
            self._script._queue_lck.release()
            self.lock_acquired = False
        super()._finish()


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
            self._script.last_triggered = utcnow()
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
                await self._async_step(log_exceptions=not propagate_exceptions)
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
            _cur_was = self._cur
            if not suspended:
                self._script.last_action = None
                await self.async_stop()
            if _cur_was != -1:
                self._changed()

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
            """Call after timeout has expired."""
            with suppress(ValueError):
                self._async_listener.remove(unsub_timeout)

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
            unsub_timeout = async_track_point_in_utc_time(
                self._hass, async_script_timeout, utcnow() + self._action[CONF_TIMEOUT]
            )
            self._async_listener.append(unsub_timeout)

        raise _SuspendScript

    async def _async_call_service_step(self):
        """Call the service specified in the action."""
        await self._hass.services.async_call(
            *self._prep_call_service_step(), blocking=True, context=self._context
        )

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
        script_mode: str = DEFAULT_SCRIPT_MODE,
        queue_max: int = DEFAULT_QUEUE_MAX,
        logger: Optional[logging.Logger] = None,
        log_exceptions: bool = True,
    ) -> None:
        """Initialize the script."""
        self._hass = hass
        self.sequence = sequence
        template.attach(hass, self.sequence)
        self.name = name
        self.change_listener = change_listener
        self._script_mode = script_mode
        if logger:
            self._logger = logger
        else:
            logger_name = __name__
            if name:
                logger_name = ".".join([logger_name, slugify(name)])
            self._logger = logging.getLogger(logger_name)
        self._log_exceptions = log_exceptions

        self.last_action = None
        self.last_triggered: Optional[datetime] = None
        self.can_cancel = not self.is_legacy or any(
            CONF_DELAY in action or CONF_WAIT_TEMPLATE in action
            for action in self.sequence
        )

        self._runs: List[_ScriptRunBase] = []
        if script_mode == SCRIPT_MODE_QUEUE:
            self._queue_max = queue_max
            self._queue_len = 0
            self._queue_lck = asyncio.Lock()
        self._config_cache: Dict[Set[Tuple], Callable[..., bool]] = {}
        self._referenced_entities: Optional[Set[str]] = None
        self._referenced_devices: Optional[Set[str]] = None

    def _changed(self):
        if self.change_listener:
            self._hass.async_run_job(self.change_listener)

    @property
    def is_running(self) -> bool:
        """Return true if script is on."""
        return len(self._runs) > 0

    @property
    def is_legacy(self) -> bool:
        """Return if using legacy mode."""
        return self._script_mode == SCRIPT_MODE_LEGACY

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
            if self._script_mode == SCRIPT_MODE_IGNORE:
                self._log("Skipping script")
                return

            if self._script_mode == SCRIPT_MODE_ERROR:
                raise AlreadyRunning

            if self._script_mode == SCRIPT_MODE_RESTART:
                self._log("Restarting script")
                await self.async_stop(update_state=False)
            elif self._script_mode == SCRIPT_MODE_QUEUE:
                self._log(
                    "Queueing script behind %i run%s",
                    self._queue_len,
                    "s" if self._queue_len > 1 else "",
                )
                if self._queue_len >= self._queue_max:
                    raise QueueFull

        if self.is_legacy:
            if self._runs:
                shared = cast(Optional[_LegacyScriptRun], self._runs[0])
            else:
                shared = None
            run: _ScriptRunBase = _LegacyScriptRun(
                self._hass, self, variables, context, self._log_exceptions, shared
            )
        else:
            if self._script_mode != SCRIPT_MODE_QUEUE:
                cls = _ScriptRun
            else:
                cls = _QueuedScriptRun
                self._queue_len += 1
            run = cls(self._hass, self, variables, context, self._log_exceptions)
        self._runs.append(run)

        try:
            if self.is_legacy:
                await run.async_run()
            else:
                await asyncio.shield(run.async_run())
        except asyncio.CancelledError:
            await run.async_stop()
            self._changed()
            raise

    async def async_stop(self, update_state: bool = True) -> None:
        """Stop running script."""
        if not self.is_running:
            return
        await asyncio.shield(asyncio.gather(*(run.async_stop() for run in self._runs)))
        if update_state:
            self._changed()

    def _log(self, msg, *args, level=logging.INFO):
        if self.name:
            msg = f"%s: {msg}"
            args = [self.name, *args]

        if level == _LOG_EXCEPTION:
            self._logger.exception(msg, *args)
        else:
            self._logger.log(level, msg, *args)
