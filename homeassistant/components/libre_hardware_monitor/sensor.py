"""Support for LibreHardwareMonitor Sensor Platform."""

from __future__ import annotations

import logging
from typing import Any

from librehardwaremonitor_api.model import DeviceId, LibreHardwareMonitorSensorData
from librehardwaremonitor_api.sensor_type import SensorType

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LibreHardwareMonitorConfigEntry, LibreHardwareMonitorCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

STATE_MIN_VALUE = "min_value"
STATE_MAX_VALUE = "max_value"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LibreHardwareMonitorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LibreHardwareMonitor platform."""
    lhm_coordinator = config_entry.runtime_data

    known_devices: set[DeviceId] = set()

    def _check_device() -> None:
        current_devices = set(lhm_coordinator.data.main_device_ids_and_names)
        new_devices = current_devices - known_devices
        if new_devices:
            _LOGGER.debug("New Device(s) detected, adding: %s", new_devices)
            known_devices.update(new_devices)
            new_devices_sensor_data = [
                sensor_data
                for sensor_data in lhm_coordinator.data.sensor_data.values()
                if sensor_data.device_id in new_devices
            ]
            async_add_entities(
                LibreHardwareMonitorSensor(
                    lhm_coordinator, config_entry.entry_id, sensor_data
                )
                for sensor_data in new_devices_sensor_data
            )

    _check_device()
    config_entry.async_on_unload(lhm_coordinator.async_add_listener(_check_device))


class LibreHardwareMonitorSensor(
    CoordinatorEntity[LibreHardwareMonitorCoordinator], SensorEntity
):
    """Sensor to display information from LibreHardwareMonitor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LibreHardwareMonitorCoordinator,
        entry_id: str,
        sensor_data: LibreHardwareMonitorSensorData,
    ) -> None:
        """Initialize an LibreHardwareMonitor sensor."""
        super().__init__(coordinator)

        self._attr_name: str = sensor_data.name

        self._set_state(coordinator.data.is_deprecated_version, sensor_data)
        self._attr_unique_id: str = f"{entry_id}_{sensor_data.sensor_id}"

        self._sensor_id: str = sensor_data.sensor_id

        # Hardware device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{sensor_data.device_id}")},
            name=f"[{coordinator.data.computer_name}] {sensor_data.device_name}",
            model=sensor_data.device_type,
        )

    def _set_state(
        self,
        is_deprecated_lhm_version: bool,
        sensor_data: LibreHardwareMonitorSensorData,
    ) -> None:
        value = sensor_data.value
        min_value = sensor_data.min
        max_value = sensor_data.max
        unit = sensor_data.unit

        if not is_deprecated_lhm_version and sensor_data.type == SensorType.THROUGHPUT:
            # Temporary fix: convert the B/s value to KB/s to not break existing entries
            # This will be migrated properly once SensorDeviceClass is introduced
            value = f"{(float(value) / 1024):.1f}" if value else None
            min_value = f"{(float(min_value) / 1024):.1f}" if min_value else None
            max_value = f"{(float(max_value) / 1024):.1f}" if max_value else None
            unit = "KB/s"

        self._attr_native_value: str | None = value
        self._attr_extra_state_attributes: dict[str, Any] = {
            STATE_MIN_VALUE: min_value,
            STATE_MAX_VALUE: max_value,
        }
        self._attr_native_unit_of_measurement = unit

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if sensor_data := self.coordinator.data.sensor_data.get(self._sensor_id):
            self._set_state(self.coordinator.data.is_deprecated_version, sensor_data)
        else:
            self._attr_native_value = None

        super()._handle_coordinator_update()
