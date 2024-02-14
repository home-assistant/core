"""Mixin class for handling harmony callback subscriptions."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import Any, NamedTuple

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)

NoParamCallback = Callable[[], Any] | None
ActivityCallback = Callable[[tuple], Any] | None


class HarmonyCallback(NamedTuple):
    """Callback type for Harmony Hub notifications."""

    connected: NoParamCallback
    disconnected: NoParamCallback
    config_updated: NoParamCallback
    activity_starting: ActivityCallback
    activity_started: ActivityCallback


class HarmonySubscriberMixin:
    """Base implementation for a subscriber."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize an subscriber."""
        super().__init__()
        self._hass = hass
        self._subscriptions: list[HarmonyCallback] = []
        self._activity_lock = asyncio.Lock()

    async def async_lock_start_activity(self) -> None:
        """Acquire the lock."""
        await self._activity_lock.acquire()

    @callback
    def async_unlock_start_activity(self) -> None:
        """Release the lock."""
        if self._activity_lock.locked():
            self._activity_lock.release()

    @callback
    def async_subscribe(self, update_callbacks: HarmonyCallback) -> CALLBACK_TYPE:
        """Add a callback subscriber."""
        self._subscriptions.append(update_callbacks)

        def _unsubscribe() -> None:
            self.async_unsubscribe(update_callbacks)

        return _unsubscribe

    @callback
    def async_unsubscribe(self, update_callback: HarmonyCallback) -> None:
        """Remove a callback subscriber."""
        self._subscriptions.remove(update_callback)

    def _config_updated(self, _: dict | None = None) -> None:
        _LOGGER.debug("config_updated")
        self._call_callbacks("config_updated")

    def _connected(self, _: str | None = None) -> None:
        _LOGGER.debug("connected")
        self.async_unlock_start_activity()
        self._available = True
        self._call_callbacks("connected")

    def _disconnected(self, _: str | None = None) -> None:
        _LOGGER.debug("disconnected")
        self.async_unlock_start_activity()
        self._available = False
        self._call_callbacks("disconnected")

    def _activity_starting(self, activity_info: tuple) -> None:
        _LOGGER.debug("activity %s starting", activity_info)
        self._call_callbacks("activity_starting", activity_info)

    def _activity_started(self, activity_info: tuple) -> None:
        _LOGGER.debug("activity %s started", activity_info)
        self.async_unlock_start_activity()
        self._call_callbacks("activity_started", activity_info)

    def _call_callbacks(
        self, callback_func_name: str, argument: tuple | None = None
    ) -> None:
        for subscription in self._subscriptions:
            current_callback = getattr(subscription, callback_func_name)
            if current_callback:
                if argument:
                    self._hass.async_run_job(current_callback, argument)
                else:
                    self._hass.async_run_job(current_callback)
