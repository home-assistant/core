"""Bluetooth coordinator that considers polling on every BM2 advertisement."""

from typing import override

from sensor_state_data import SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_register_advertisement_callback,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.core import CALLBACK_TYPE, callback


class BMxBluetoothCoordinator(ActiveBluetoothProcessorCoordinator[SensorUpdate]):
    """Active coordinator that also sees advertisements HA deduplicates.

    A BM2 can repeat an identical advertisement for hours, which never reaches
    the coordinator's own Bluetooth callback, so reads would otherwise stall.
    """

    @callback
    @override
    def async_start(self) -> CALLBACK_TYPE:
        """Start Bluetooth subscriptions, including every raw advertisement."""
        cancel_coordinator = super().async_start()
        cancel_advertisements = async_register_advertisement_callback(
            self.hass, self._async_poll_if_needed, self.address
        )

        @callback
        def _async_cancel() -> None:
            cancel_advertisements()
            cancel_coordinator()

        return _async_cancel

    @callback
    def _async_poll_if_needed(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Schedule a debounced read when this advertisement makes one due."""
        if self.needs_poll(service_info):
            self._last_service_info = service_info
            self._debounced_poll.async_schedule_call()
