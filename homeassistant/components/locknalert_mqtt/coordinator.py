"""State coordinator for LocknAlert entities."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import CALLBACK_TYPE, callback


@dataclass(slots=True)
class LocknAlertState:
    """Normalized runtime state."""

    available: bool = False
    bridge: dict[str, Any] = field(default_factory=dict)
    zones: dict[str, dict[str, Any]] = field(default_factory=dict)
    partitions: dict[str, dict[str, Any]] = field(default_factory=dict)
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    sensors: dict[str, dict[str, Any]] = field(default_factory=dict)


class LocknAlertCoordinator:
    """Central state holder and pub/sub dispatcher.

    Pattern adapted from HA LocknAlertLocknAlertMQTT internals: one message pump and many subscribers.
    """

    def __init__(self) -> None:
        self.state = LocknAlertState()
        self._listeners: dict[str, set[Callable[[], None]]] = defaultdict(set)

    @callback
    def async_listen(self, channel: str, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners[channel].add(listener)

        @callback
        def _remove_listener() -> None:
            self._listeners[channel].discard(listener)

        return _remove_listener

    @callback
    def async_update(self, channel: str, payload: dict[str, Any]) -> None:
        if channel == "availability":
            self.state.available = payload.get("state") == "online"
        elif channel == "status":
            self.state.bridge = payload
        elif channel.startswith("zone:"):
            self.state.zones[channel.split(":", 1)[1]] = payload
        elif channel.startswith("partition:"):
            self.state.partitions[channel.split(":", 1)[1]] = payload
        elif channel.startswith("output:"):
            self.state.outputs[channel.split(":", 1)[1]] = payload
        elif channel.startswith("sensor:"):
            self.state.sensors[channel.split(":", 1)[1]] = payload

        for listener in list(self._listeners.get(channel, set())):
            listener()
        for listener in list(self._listeners.get("*", set())):
            listener()
