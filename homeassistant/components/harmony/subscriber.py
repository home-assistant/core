"""Mixin class for handling harmony callback subscriptions."""

import asyncio
import logging
from typing import Any, Callable, NamedTuple, Optional

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

NoParamCallback = Optional[Callable[[object], Any]]
ActivityCallback = Optional[Callable[[object, tuple], Any]]


class HarmonyCallback(NamedTuple):
    """Callback type for Harmony Hub notifications."""

    connected: NoParamCallback
    disconnected: NoParamCallback
    config_updated: NoParamCallback
    activity_starting: ActivityCallback
    activity_started: ActivityCallback


class HarmonySubscriberMixin:
    """Base implementation for a subscriber."""

    def __init__(self):
        """Initialize an subscriber."""
        super().__init__()
        self._subscriptions = []

    @callback
    def async_subscribe(self, update_callback: HarmonyCallback) -> Callable:
        """Add a callback subscriber."""
        self._subscriptions.append(update_callback)

        def _unsubscribe():
            self.async_unsubscribe(update_callback)

        return _unsubscribe

    @callback
    def async_unsubscribe(self, update_callback: HarmonyCallback):
        """Remove a callback subscriber."""
        self._subscriptions.remove(update_callback)

    def _config_updated(self, _=None) -> None:
        _LOGGER.debug("config_updated")
        for subscription in self._subscriptions:
            current_callback = subscription.config_updated
            if current_callback:
                if asyncio.iscoroutinefunction(current_callback):
                    asyncio.create_task(current_callback())
                else:
                    current_callback()

    def _connected(self, _=None) -> None:
        _LOGGER.debug("connected")
        self._available = True
        for subscription in self._subscriptions:
            current_callback = subscription.connected
            if current_callback:
                if asyncio.iscoroutinefunction(current_callback):
                    asyncio.create_task(current_callback())
                else:
                    current_callback()

    def _disconnected(self, _=None) -> None:
        _LOGGER.debug("disconnected")
        self._available = False
        for subscription in self._subscriptions:
            current_callback = subscription.disconnected
            if current_callback:
                if asyncio.iscoroutinefunction(current_callback):
                    asyncio.create_task(current_callback())
                else:
                    current_callback()

    def _activity_starting(self, activity_info: tuple) -> None:
        _LOGGER.debug("activity %s starting", activity_info)
        for subscription in self._subscriptions:
            current_callback = subscription.activity_starting
            if current_callback:
                if asyncio.iscoroutinefunction(current_callback):
                    asyncio.create_task(current_callback(activity_info))
                else:
                    current_callback(activity_info)

    def _activity_started(self, activity_info: tuple) -> None:
        _LOGGER.debug("activity %s started", activity_info)
        for subscription in self._subscriptions:
            current_callback = subscription.activity_started
            if current_callback:
                if asyncio.iscoroutinefunction(current_callback):
                    asyncio.create_task(current_callback(activity_info))
                else:
                    current_callback(activity_info)
