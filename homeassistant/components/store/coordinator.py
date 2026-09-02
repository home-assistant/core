"""Coordinator to trigger entity updates."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.update_coordinator import BaseDataUpdateCoordinatorProtocol


class HacsUpdateCoordinator(BaseDataUpdateCoordinatorProtocol):
    """Dispatch updates to update entities."""

    def __init__(self) -> None:
        """Initialize."""
        self._listeners: dict[CALLBACK_TYPE, tuple[CALLBACK_TYPE, object | None]] = {}

    @callback
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> Callable[[], None]:
        """Listen for data updates."""

        @callback
        def remove_listener() -> None:
            """Remove update listener."""
            self._listeners.pop(remove_listener)

        self._listeners[remove_listener] = (update_callback, context)

        return remove_listener

    @callback
    def async_update_listeners(self) -> None:
        """Update all registered listeners."""
        for update_callback, _ in list(self._listeners.values()):
            update_callback()
