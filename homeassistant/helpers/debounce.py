"""Debounce helper."""
import asyncio
from logging import Logger
from typing import Any, Awaitable, Callable, Optional

from homeassistant.core import HomeAssistant, callback


class Debouncer:
    """Class to rate limit calls to a specific command."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        cooldown: float,
        immediate: bool,
        function: Optional[Callable[..., Awaitable[Any]]] = None,
    ):
        """Initialize debounce.

        immediate: indicate if the function needs to be called right away and
                   wait 0.3s until executing next invocation.
        function: optional and can be instantiated later.
        """
        self.hass = hass
        self.logger = logger
        self.function = function
        self.cooldown = cooldown
        self.immediate = immediate
        self._timer_task: Optional[asyncio.TimerHandle] = None
        self._execute_at_end_of_timer: bool = False
        self._execute_lock = asyncio.Lock()

    async def async_call(self) -> None:
        """Call the function."""
        assert self.function is not None

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

            await self.hass.async_add_job(self.function)  # type: ignore

            self._schedule_timer()

    async def _handle_timer_finish(self) -> None:
        """Handle a finished timer."""
        assert self.function is not None

        self._timer_task = None

        if not self._execute_at_end_of_timer:
            return

        self._execute_at_end_of_timer = False

        # Locked means a call is in progress. Any call is good, so abort.
        if self._execute_lock.locked():
            return

        async with self._execute_lock:
            # Abort if timer got set while we're waiting for the lock.
            if self._timer_task:
                return  # type: ignore

            try:
                await self.hass.async_add_job(self.function)  # type: ignore
            except Exception:  # pylint: disable=broad-except
                self.logger.exception("Unexpected exception from %s", self.function)

            self._schedule_timer()

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
        self._timer_task = self.hass.loop.call_later(
            self.cooldown,
            lambda: self.hass.async_create_task(self._handle_timer_finish()),
        )
