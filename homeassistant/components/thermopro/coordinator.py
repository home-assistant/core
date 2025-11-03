"""Coordinator for the ThermoPro Bluetooth integration."""

from __future__ import annotations

from logging import Logger

from thermopro_ble import SensorUpdate, ThermoProBluetoothDeviceData

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
        update = self.device_data.update(service_info)
        async_dispatcher_send(
            self.hass,
            f"{SIGNAL_DATA_UPDATED}_{self.entry.entry_id}",
            self.device_data,
            service_info,
            update,
        )
        return update
