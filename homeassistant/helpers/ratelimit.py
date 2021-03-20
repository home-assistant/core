"""Ratelimit helper."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, Callable, Hashable

from homeassistant.core import HomeAssistant, callback
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


class KeyedRateLimit:
    """Class to track rate limits."""

    def __init__(
        self,
        hass: HomeAssistant,
    ):
        """Initialize ratelimit tracker."""
        self.hass = hass
        self._last_triggered: dict[Hashable, datetime] = {}
        self._rate_limit_timers: dict[Hashable, asyncio.TimerHandle] = {}

    @callback
    def async_has_timer(self, key: Hashable) -> bool:
        """Check if a rate limit timer is running."""
        if not self._rate_limit_timers:
            return False
        return key in self._rate_limit_timers

    @callback
    def async_triggered(self, key: Hashable, now: datetime | None = None) -> None:
        """Call when the action we are tracking was triggered."""
        self.async_cancel_timer(key)
        self._last_triggered[key] = now or dt_util.utcnow()

    @callback
    def async_cancel_timer(self, key: Hashable) -> None:
        """Cancel a rate limit time that will call the action."""
        if not self._rate_limit_timers or not self.async_has_timer(key):
            return

        self._rate_limit_timers.pop(key).cancel()

    @callback
    def async_remove(self) -> None:
        """Remove all timers."""
        for timer in self._rate_limit_timers.values():
            timer.cancel()
        self._rate_limit_timers.clear()

    @callback
    def async_schedule_action(
        self,
        key: Hashable,
        rate_limit: timedelta | None,
        now: datetime,
        action: Callable,
        *args: Any,
    ) -> datetime | None:
        """Check rate limits and schedule an action if we hit the limit.

        If the rate limit is hit:
            Schedules the action for when the rate limit expires
            if there are no pending timers. The action must
            be called in async.

            Returns the time the rate limit will expire

        If the rate limit is not hit:

            Return None
        """
        if rate_limit is None:
            return None

        last_triggered = self._last_triggered.get(key)
        if not last_triggered:
            return None

        next_call_time = last_triggered + rate_limit

        if next_call_time <= now:
            self.async_cancel_timer(key)
            return None

        _LOGGER.debug(
            "Reached rate limit of %s for %s and deferred action until %s",
            rate_limit,
            key,
            next_call_time,
        )

        if key not in self._rate_limit_timers:
            self._rate_limit_timers[key] = self.hass.loop.call_later(
                (next_call_time - now).total_seconds(),
                action,
                *args,
            )

        return next_call_time
