"""Schedule an active read or passive fallback, respecting rate limits."""

from datetime import datetime, timedelta
from typing import override

from bluetooth_data_tools import monotonic_time_coarse
from sensor_state_data import SensorUpdate

from homeassistant.components.bluetooth import (
    async_address_present,
    async_last_service_info,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.core import CALLBACK_TYPE, CoreState, callback
from homeassistant.helpers.event import async_track_time_interval

FALLBACK_CHECK_INTERVAL = timedelta(seconds=10)
FALLBACK_POLL_INTERVAL = 60


class BMxBluetoothCoordinator(ActiveBluetoothProcessorCoordinator[SensorUpdate]):
    """Use one debouncer for advertisement-triggered and fallback reads."""

    _cancel_fallback: CALLBACK_TYPE | None = None

    @callback
    @override
    def async_start(self) -> CALLBACK_TYPE:
        """Start Bluetooth subscriptions and the fallback timer."""
        cancel = super().async_start()
        self._cancel_fallback = async_track_time_interval(
            self.hass, self._async_schedule_poll, FALLBACK_CHECK_INTERVAL
        )
        return cancel

    @callback
    def _async_schedule_poll(self, _: datetime) -> None:
        """Request an active read after a quiet interval, respecting rate limits."""
        if self.hass.state is not CoreState.running or self.hass.is_stopping:
            return
        if not async_address_present(self.hass, self.address, connectable=False):
            return
        service_info = async_last_service_info(
            self.hass, self.address, connectable=False
        )
        if service_info is None:
            return
        # Cached service-info timestamps may stop advancing after deduplication.
        age = (
            monotonic_time_coarse() - self._last_poll
            if self._last_poll is not None
            else None
        )
        if age is not None and age < FALLBACK_POLL_INTERVAL:
            return
        if not self._needs_poll_method(service_info, age):
            return
        self._last_service_info = service_info
        self._debounced_poll.async_schedule_call()

    @callback
    @override
    def _async_stop(self) -> None:
        """Cancel the fallback timer and pending Bluetooth reads."""
        if self._cancel_fallback is not None:
            self._cancel_fallback()
            self._cancel_fallback = None
        super()._async_stop()
