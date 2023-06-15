"""Debounce helper."""
from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Callable
from logging import Logger
from typing import Any, Generic, TypeVar

from homeassistant.core import HassJob, HomeAssistant, callback, is_callback

_R_co = TypeVar("_R_co", covariant=True)


class DebouncerBase(Generic[_R_co]):
    """Class to rate limit calls to a specific command."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        cooldown: float,
        immediate: bool,
        function: Callable[[], _R_co] | None = None,
    ) -> None:
        """Initialize debounce.

        immediate: indicate if the function needs to be called right away and
                   wait <cooldown> until executing next invocation.
        function: optional and can be instantiated later.
        """
        self.hass = hass
        self.logger = logger
        self._function = function
        self.cooldown = cooldown
        self.immediate = immediate
        self._timer_task: asyncio.TimerHandle | None = None
        self._execute_at_end_of_timer: bool = False
        self._job: HassJob[[], _R_co] | None = (
            None
            if function is None
            else HassJob(
                function, f"debouncer cooldown={cooldown}, immediate={immediate}"
            )
        )
        self._shutdown_requested = False

    @property
    def function(self) -> Callable[[], _R_co] | None:
        """Return the function being wrapped by the Debouncer."""
        return self._function

    @function.setter
    def function(self, function: Callable[[], _R_co]) -> None:
        """Update the function being wrapped by the Debouncer."""
        self._function = function
        if self._job is None or function != self._job.target:
            self._job = HassJob(
                function,
                f"debouncer cooldown={self.cooldown}, immediate={self.immediate}",
            )

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and prevent new runs."""
        self._shutdown_requested = True
        self.async_cancel()

    @callback
    def async_cancel(self) -> None:
        """Cancel any scheduled call."""
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None

        self._execute_at_end_of_timer = False

    @callback
    def _schedule_timer(self) -> None:
        """Schedule a timer."""
        if not self._shutdown_requested:
            self._timer_task = self.hass.loop.call_later(
                self.cooldown, self._on_debounce
            )

    def _execute_job_schedule_next(
        self, raise_exception: bool
    ) -> asyncio.Future[Any] | None:
        """Execute the job and schedule the next call."""
        assert self._job is not None
        try:
            return self.hass.async_run_hass_job(self._job)
        except Exception:  # pylint: disable=broad-except
            if raise_exception:
                raise
            self.logger.exception("Unexpected exception from %s", self.function)
        finally:
            # Schedule a new timer to prevent new runs during cooldown
            self._schedule_timer()
        return None

    @callback
    @abstractmethod
    def _on_debounce(self) -> None:
        """Create job, but only if pending."""


class Debouncer(DebouncerBase[_R_co]):
    """Class to rate limit calls to a specific command."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        cooldown: float,
        immediate: bool,
        function: Callable[[], _R_co] | None = None,
    ) -> None:
        """Initialize debounce."""
        super().__init__(
            hass, logger, cooldown=cooldown, immediate=immediate, function=function
        )
        self._execute_lock = asyncio.Lock()

    async def async_call(self) -> None:
        """Call the function."""
        if self._shutdown_requested:
            self.logger.warning(
                "Debouncer call ignored as shutdown has been requested."
            )
            return

        if self._timer_task:
            self._execute_at_end_of_timer = True
            return

        # Locked means a call is in progress. Any call is good, so abort.
        if self._execute_lock.locked():
            return

        if not self.immediate:
            self._execute_at_end_of_timer = True
            self._schedule_timer()
            return

        async with self._execute_lock:
            # Abort if timer got set while we're waiting for the lock.
            if self._timer_task:
                return
            if task := self._execute_job_schedule_next(True):
                await task

    async def _handle_timer_finish(self) -> None:
        """Handle a finished timer."""
        self._execute_at_end_of_timer = False

        # Locked means a call is in progress. Any call is good, so abort.
        if self._execute_lock.locked():
            return

        async with self._execute_lock:
            # Abort if timer got set while we're waiting for the lock.
            if self._timer_task:
                return
            if task := self._execute_job_schedule_next(False):
                await task

    @callback
    def _on_debounce(self) -> None:
        """Create job task, but only if pending."""
        self._timer_task = None
        if self._execute_at_end_of_timer:
            self.hass.async_create_task(
                self._handle_timer_finish(),
                f"debouncer {self._job} finish cooldown={self.cooldown}, immediate={self.immediate}",
            )


class CallbackDebouncer(DebouncerBase[_R_co]):
    """A debouncer implementation that uses callbacks and no coroutines."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        cooldown: float,
        immediate: bool,
        function: Callable[[], _R_co] | None = None,
    ) -> None:
        """Initialize debounce."""
        if function and not is_callback(function):
            raise ValueError("Function must be a callback.")
        super().__init__(
            hass, logger, cooldown=cooldown, immediate=immediate, function=function
        )

    @callback
    def async_call(self) -> None:
        """Call the function."""
        if self._shutdown_requested:
            self.logger.warning(
                "Debouncer call ignored as shutdown has been requested."
            )
            return

        if self._timer_task:
            self._execute_at_end_of_timer = True
            return

        if not self.immediate:
            self._execute_at_end_of_timer = True
            self._schedule_timer()
            return

        self._execute_job_schedule_next(True)

    @callback
    def _on_debounce(self) -> None:
        """Create job, but only if pending."""
        self._timer_task = None
        if not self._execute_at_end_of_timer:
            return
        self._execute_at_end_of_timer = False
        self._execute_job_schedule_next(False)
