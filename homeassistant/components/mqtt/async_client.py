"""Async wrappings for mqtt client."""

from __future__ import annotations

from functools import lru_cache
from types import TracebackType
from typing import Self

from paho.mqtt.client import (
    CallbackOnConnect_v2,
    CallbackOnDisconnect_v2,
    CallbackOnPublish_v2,
    CallbackOnSubscribe_v2,
    CallbackOnUnsubscribe_v2,
    Client as MQTTClient,
)

_MQTT_LOCK_COUNT = 7


class NullLock:
    """Null lock."""

    @lru_cache(maxsize=_MQTT_LOCK_COUNT)
    def __enter__(self) -> Self:
        """Enter the lock."""
        return self

    @lru_cache(maxsize=_MQTT_LOCK_COUNT)
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit the lock."""

    @lru_cache(maxsize=_MQTT_LOCK_COUNT)
    def acquire(self, blocking: bool = False, timeout: int = -1) -> None:
        """Acquire the lock."""

    @lru_cache(maxsize=_MQTT_LOCK_COUNT)
    def release(self) -> None:
        """Release the lock."""


class AsyncMQTTClient(MQTTClient):
    """Async MQTT Client.

    Wrapper around paho.mqtt.client.Client to remove the locking
    that is not needed since we are running in an async event loop.
    """

    on_connect: CallbackOnConnect_v2
    on_disconnect: CallbackOnDisconnect_v2
    on_publish: CallbackOnPublish_v2
    on_subscribe: CallbackOnSubscribe_v2
    on_unsubscribe: CallbackOnUnsubscribe_v2

    def setup(self) -> None:
        """Set up the client.

        All the threading locks are replaced with NullLock
        since the client is running in an async event loop
        and will never run in multiple threads.
        """
        self._in_callback_mutex = NullLock()  # type: ignore[assignment]
        self._callback_mutex = NullLock()  # type: ignore[assignment]
        self._msgtime_mutex = NullLock()  # type: ignore[assignment]
        self._out_message_mutex = NullLock()  # type: ignore[assignment]
        self._in_message_mutex = NullLock()  # type: ignore[assignment]
        self._reconnect_delay_mutex = NullLock()  # type: ignore[assignment]
        self._mid_generate_mutex = NullLock()  # type: ignore[assignment]
