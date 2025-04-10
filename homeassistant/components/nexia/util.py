"""Utils for Nexia / Trane XL Thermostats."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
from http import HTTPStatus
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later


def is_invalid_auth_code(http_status_code):
    """HTTP status codes that mean invalid auth."""
    if http_status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        return True

    return False


def percent_conv(val):
    """Convert an actual percentage (0.0-1.0) to 0-100 scale."""
    if val is None:
        return None
    return round(val * 100.0, 1)


class SingleShot:
    """Provides a single shot timer that can be reset.

    Fires a while following the *last* call to `reset_delayed_action_trigger`.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        delay: timedelta,
        delayed_call: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Initialize this single shot timer."""
        self._hass = hass
        self._delay = delay
        self._delayed_call = delayed_call
        self._cancel_delayed_action: Callable[[], None] | None = None
        self._execute_lock = asyncio.Lock()
        self._shutting_down = False
        self._job = HassJob(
            self._delayed_action,
            f"resettable single shot action {self._delay}",
        )
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_shutdown)

    async def _delayed_action(self, now: Any) -> None:
        """Perform the action now that the delay has completed."""
        self._cancel_delayed_action = None

        async with self._execute_lock:
            # Abort if rescheduled while waiting for the lock or shutting down.
            if self._cancel_delayed_action or self._shutting_down:
                return

            # Perform the primary action for this timer.
            await self._delayed_call()

    def reset_delayed_action_trigger(self) -> None:
        """Set or reset the delayed action trigger.

        Perform the action a while after this call.
        """
        if self._shutting_down:
            return
        if self._cancel_delayed_action:
            self._cancel_delayed_action()

        self._cancel_delayed_action = async_call_later(
            self._hass, self._delay, self._job
        )

    @callback
    def _async_shutdown(self, event: Any) -> None:
        """Handle Home Assistant stopping."""
        self._shutting_down = True
        if self._cancel_delayed_action:
            self._cancel_delayed_action()
            self._cancel_delayed_action = None
        self._delayed_call = None
