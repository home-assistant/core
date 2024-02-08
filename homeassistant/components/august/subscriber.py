"""Base class for August entity."""
from __future__ import annotations

from abc import abstractmethod
from datetime import datetime, timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval


class AugustSubscriberMixin:
    """Base implementation for a subscriber."""

    def __init__(self, hass: HomeAssistant, update_interval: timedelta) -> None:
        """Initialize an subscriber."""
        super().__init__()
        self._hass = hass
        self._update_interval = update_interval
        self._subscriptions: dict[str, list[CALLBACK_TYPE]] = {}
        self._unsub_interval: CALLBACK_TYPE | None = None
        self._stop_interval: CALLBACK_TYPE | None = None

    @callback
    def async_subscribe_device_id(
        self, device_id: str, update_callback: CALLBACK_TYPE
    ) -> CALLBACK_TYPE:
        """Add an callback subscriber.

        Returns a callable that can be used to unsubscribe.
        """
        if not self._subscriptions:
            self._async_setup_listeners()

        self._subscriptions.setdefault(device_id, []).append(update_callback)

        def _unsubscribe() -> None:
            self.async_unsubscribe_device_id(device_id, update_callback)

        return _unsubscribe

    @abstractmethod
    async def _async_refresh(self, time: datetime) -> None:
        """Refresh data."""

    @callback
    def _async_setup_listeners(self) -> None:
        """Create interval and stop listeners."""
        self._unsub_interval = async_track_time_interval(
            self._hass,
            self._async_refresh,
            self._update_interval,
            name="august refresh",
        )

        @callback
        def _async_cancel_update_interval(_: Event) -> None:
            self._stop_interval = None
            if self._unsub_interval:
                self._unsub_interval()

        self._stop_interval = self._hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, _async_cancel_update_interval
        )

    @callback
    def async_unsubscribe_device_id(
        self, device_id: str, update_callback: CALLBACK_TYPE
    ) -> None:
        """Remove a callback subscriber."""
        self._subscriptions[device_id].remove(update_callback)
        if not self._subscriptions[device_id]:
            del self._subscriptions[device_id]

        if self._subscriptions:
            return

        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None
        if self._stop_interval:
            self._stop_interval()
            self._stop_interval = None

    @callback
    def async_signal_device_id_update(self, device_id: str) -> None:
        """Call the callbacks for a device_id."""
        if not self._subscriptions.get(device_id):
            return

        for update_callback in self._subscriptions[device_id]:
            update_callback()
