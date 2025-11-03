"""Coordinator for the ThermoPro Bluetooth integration."""

from __future__ import annotations

from logging import Logger

from thermopro_ble import SensorUpdate, ThermoProBluetoothDeviceData

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import SIGNAL_DATA_UPDATED

type ThermoProConfigEntry = ConfigEntry["ThermoProBluetoothProcessorCoordinator"]


class ThermoProBluetoothProcessorCoordinator(
    PassiveBluetoothProcessorCoordinator[SensorUpdate]
):
    """Passive update coordinator that tracks ThermoPro advertisements."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        address: str,
        mode: BluetoothScanningMode,
        device_data: ThermoProBluetoothDeviceData,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.device_data = device_data
        self.entry = entry
        self._rediscovery_pending = False
        super().__init__(
            hass,
            logger,
            address=address,
            mode=mode,
            update_method=self._process_service_info,
            connectable=False,
        )

    def _process_service_info(
        self, service_info: BluetoothServiceInfoBleak
    ) -> SensorUpdate:
        """Process an incoming Bluetooth advertisement."""
        self._rediscovery_pending = False
        update = self.device_data.update(service_info)
        async_dispatcher_send(
            self.hass,
            f"{SIGNAL_DATA_UPDATED}_{self.entry.entry_id}",
            self.device_data,
            service_info,
            update,
        )
        return update

    def restore_service_info(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Restore state from the last received Bluetooth advertisement."""
        self.async_set_updated_data(self._process_service_info(service_info))

    def _process_update(
        self, update: SensorUpdate, was_available: bool | None = None
    ) -> None:
        """Process data update and clear rediscovery state."""
        self._rediscovery_pending = False
        super()._process_update(update, was_available)

    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Handle device unavailable events."""
        super()._async_handle_unavailable(service_info)
        if not self._rediscovery_pending:
            self._rediscovery_pending = True
            bluetooth.async_rediscover_address(self.hass, self.address)
