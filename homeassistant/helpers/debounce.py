"""Debounce helper."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from logging import Logger
from typing import Generic, TypeVar

from homeassistant.core import HassJob, HomeAssistant, callback

_R_co = TypeVar("_R_co", covariant=True)


class Debouncer(Generic[_R_co]):
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
        self._execute_lock = asyncio.Lock()
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

    async def async_call(self) -> None:
        """Call the function."""
        if self._shutdown_requested:
            self.logger.warning(
                "Debouncer call ignored as shutdown has been requested."
            )
            return
        assert self._job is not None

        if self._timer_task:
            if not self._execute_at_end_of_timer:
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

            task = self.hass.async_run_hass_job(self._job)
            if task:
                await task

            self._schedule_timer()

    async def _handle_timer_finish(self) -> None:
        """Handle a finished timer."""
        assert self._job is not None

        self._execute_at_end_of_timer = False

        # Locked means a call is in progress. Any call is good, so abort.
        if self._execute_lock.locked():
            return

        async with self._execute_lock:
            # Abort if timer got set while we're waiting for the lock.
            if self._timer_task:
                return

            try:
                task = self.hass.async_run_hass_job(self._job)
                if task:
                    await task
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Unexpected exception from %s", self.function)

            # Schedule a new timer to prevent new runs during cooldown
            self._schedule_timer()

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
    def _on_debounce(self) -> None:
        """Create job task, but only if pending."""
        self._timer_task = None
        if self._execute_at_end_of_timer:
            self.hass.async_create_task(
                self._handle_timer_finish(),
                f"debouncer {self._job} finish cooldown={self.cooldown}, immediate={self.immediate}",
            )

    @callback
    def _schedule_timer(self) -> None:
        """Schedule a timer."""
        if not self._shutdown_requested:
            self._timer_task = self.hass.loop.call_later(
                self.cooldown, self._on_debounce
            )
