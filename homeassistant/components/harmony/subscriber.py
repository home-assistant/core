"""Harmony callback subscriber."""

import logging
from typing import Any, Callable, NamedTuple, Optional

from aioharmony.const import ClientCallbackType
import aioharmony.exceptions as aioexc
from aioharmony.harmonyapi import HarmonyAPI as HarmonyClient

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


class HarmonySubscriber:
    """Subscriber for Harmony hub updates."""

    def __init__(self, client: HarmonyClient, name: str):
        """Initialize a subscriber."""
        self._client = client
        self._name = name
        self._subscriptions = []

        callbacks = {
            "config_updated": self._config_updated,
            "connect": self._connected,
            "disconnect": self._disconnected,
            "new_activity_starting": self._activity_starting,
            "new_activity": self._activity_started,
        }
        self._client.callbacks = ClientCallbackType(**callbacks)

    async def connect(self) -> bool:
        """Connect to the Harmony Hub."""
        _LOGGER.debug("%s: Connecting", self._name)
        try:
            if not await self._client.connect():
                _LOGGER.warning("%s: Unable to connect to HUB", self._name)
                await self._client.close()
                return False
        except aioexc.TimeOut:
            _LOGGER.warning("%s: Connection timed-out", self._name)
            return False
        return True

    async def shutdown(self):
        """Close connection on shutdown."""
        _LOGGER.debug("%s: Closing Harmony Hub", self._name)
        try:
            await self._client.close()
        except aioexc.TimeOut:
            _LOGGER.warning("%s: Disconnect timed-out", self._name)

    @callback
    def async_subscribe(self, update_callback: HarmonyCallback):
        """Add a callback subscriber."""
        self._subscriptions.append(update_callback)

        def _unsubscribe():
            self.async_unsubscribe(update_callback)

        return _unsubscribe()

    @callback
    def async_unsubscribe_hub_id(self, update_callback: HarmonyCallback):
        """Remove a callback subscriber."""
        self._subscriptions.remove(update_callback)

    def _config_updated(self, _=None) -> None:
        for subscription in self._subscriptions:
            callback = subscription.config_updated
            if callback:
                callback()

    def _connected(self, _=None) -> None:
        for subscription in self._subscriptions:
            callback = subscription.connected
            if callback:
                callback()

    def _disconnected(self, _=None) -> None:
        for subscription in self._subscriptions:
            callback = subscription.disconnected
            if callback:
                callback()

    def _activity_starting(self, activity_info: tuple) -> None:
        for subscription in self._subscriptions:
            callback = subscription.activity_starting
            if callback:
                callback(activity_info)

    def _activity_started(self, activity_info: tuple) -> None:
        for subscription in self._subscriptions:
            callback = subscription.activity_started
            if callback:
                callback(activity_info)
