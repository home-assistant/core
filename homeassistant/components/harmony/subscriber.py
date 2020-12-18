"""Mixin class for handling harmony callback subscriptions."""

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

    def __init__(self, hass):
        """Initialize an subscriber."""
        super().__init__()
        self._hass = hass
        self._subscriptions = []

    @callback
    def async_subscribe(self, update_callbacks: HarmonyCallback) -> Callable:
        """Add a callback subscriber."""
        self._subscriptions.append(update_callbacks)

        def _unsubscribe():
            self.async_unsubscribe(update_callbacks)

        return _unsubscribe

    @callback
    def async_unsubscribe(self, update_callback: HarmonyCallback):
        """Remove a callback subscriber."""
        self._subscriptions.remove(update_callback)

    def _config_updated(self, _=None) -> None:
        _LOGGER.debug("config_updated")
        self._call_callbacks("config_updated")

    def _connected(self, _=None) -> None:
        _LOGGER.debug("connected")
        self._available = True
        self._call_callbacks("connected")

    def _disconnected(self, _=None) -> None:
        _LOGGER.debug("disconnected")
        self._available = False
        self._call_callbacks("disconnected")

    def _activity_starting(self, activity_info: tuple) -> None:
        _LOGGER.debug("activity %s starting", activity_info)
        self._call_callbacks("activity_starting", activity_info)

    def _activity_started(self, activity_info: tuple) -> None:
        _LOGGER.debug("activity %s started", activity_info)
        self._call_callbacks("activity_started", activity_info)

    def _call_callbacks(self, callback_func_name: str, argument: tuple = None):
        for subscription in self._subscriptions:
            current_callback = getattr(subscription, callback_func_name)
            if current_callback:
                if argument:
                    self._hass.async_run_job(current_callback, argument)
                else:
                    self._hass.async_run_job(current_callback)
