"""Data coordinator for the HEMS Echonet Lite integration."""

from __future__ import annotations

from collections.abc import Callable
import logging

from pyhems import DeviceManager, HemsFrameEvent, HemsInstanceListEvent, NodeState

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .types import EchonetLiteConfigEntry

_LOGGER = logging.getLogger(__name__)


class EchonetLiteCoordinator(DataUpdateCoordinator[dict[str, NodeState]]):
    """Coordinator that tracks state for detected SEOJ nodes.

    Delegates device management (discovery, frame processing, property tracking)
    to pyhems DeviceManager. This coordinator acts as a thin bridge between
    DeviceManager and Home Assistant's DataUpdateCoordinator pattern.
    """

    config_entry: EchonetLiteConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: EchonetLiteConfigEntry,
        device_manager: DeviceManager,
    ) -> None:
        """Initialize the coordinator for a specific config entry."""

        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_coordinator",
            update_interval=None,
            config_entry=config_entry,
        )
        # ``async_set_updated_data`` is the canonical way to publish data on
        # ``DataUpdateCoordinator``. ``async_setup_entry`` seeds the empty
        # snapshot right after startup; this default keeps ``.data`` iterable
        # for callers (and tests) that inspect it before the first update.
        self.data: dict[str, NodeState] = {}
        self._last_runtime_activity_at: float | None = None
        self.device_manager = device_manager
        self._device_added_listeners: list[Callable[[str], None]] = []

    @property
    def last_runtime_activity_at(self) -> float | None:
        """Return the timestamp of the last runtime activity seen by HA."""
        return self._last_runtime_activity_at

    def record_runtime_activity(self, timestamp: float) -> None:
        """Record the timestamp of the latest runtime activity."""
        self._last_runtime_activity_at = timestamp

    @callback
    def async_add_device_added_listener(
        self, listener: Callable[[str], None]
    ) -> Callable[[], None]:
        """Register a listener invoked when a new device becomes known.

        The listener receives the ``device_key`` of the newly added device.
        Returns an unsubscribe callable.
        """
        self._device_added_listeners.append(listener)

        @callback
        def _unsubscribe() -> None:
            if listener in self._device_added_listeners:
                self._device_added_listeners.remove(listener)

        return _unsubscribe

    @callback
    def async_notify_device_added(self, device_key: str) -> None:
        """Notify all device-added listeners about a newly added device."""
        for listener in list(self._device_added_listeners):
            listener(device_key)

    async def async_process_frame_event(self, event: HemsFrameEvent) -> None:
        """Process a frame event via DeviceManager and notify listeners if updated."""
        self.device_manager.process_frame_event(event)

    async def async_process_instance_list_event(
        self, event: HemsInstanceListEvent
    ) -> None:
        """Process an instance list event via DeviceManager.

        New devices are set up by DeviceManager. The on_device_added callback
        (registered in __init__.py) handles notifying HA listeners.
        """
        await self.device_manager.process_instance_list_event(event)
