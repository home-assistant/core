"""Coordinator for the Chef iQ integration."""

from typing import override

from chefiq_ble import SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.core import callback


class ChefIqPassiveBluetoothProcessorCoordinator(
    PassiveBluetoothProcessorCoordinator[SensorUpdate]
):
    """Passive coordinator that logs once when the probe stops and resumes broadcasting.

    A probe stops advertising when it is docked, so its sensors become
    unavailable after the stale-advertisement window and come back with the
    next advertisement. Each transition is logged once.
    """

    _unavailable_logged = False

    @callback
    @override
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Handle the probe going unavailable."""
        super()._async_handle_unavailable(service_info)
        if not self._unavailable_logged:
            self._unavailable_logged = True
            self.logger.info(
                "Chef iQ probe %s stopped broadcasting; its sensors are unavailable",
                self.address,
            )

    @callback
    @override
    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        super()._async_handle_bluetooth_event(service_info, change)
        if self._unavailable_logged and self.available:
            self._unavailable_logged = False
            self.logger.info("Chef iQ probe %s is broadcasting again", self.address)
