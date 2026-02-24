"""Support for LibreHardwareMonitor Sensor Platform."""

import logging
from typing import Any, override

from librehardwaremonitor_api.model import DeviceId, LibreHardwareMonitorSensorData
from librehardwaremonitor_api.sensor_type import SensorType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate
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
        self._attr_device_class = self._map_device_class(sensor_data)

        self._set_state(sensor_data)
        self._attr_unique_id: str = f"{entry_id}_{sensor_data.sensor_id}"

        self._sensor_id: str = sensor_data.sensor_id

        # Hardware device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{sensor_data.device_id}")},
            name=f"[{coordinator.data.computer_name}] {sensor_data.device_name}",
            model=sensor_data.device_type,
        )

    def _set_state(self, sensor_data: LibreHardwareMonitorSensorData) -> None:
        self._attr_native_value: str | None = sensor_data.value
        self._attr_extra_state_attributes: dict[str, Any] = {
            STATE_MIN_VALUE: sensor_data.min,
            STATE_MAX_VALUE: sensor_data.max,
        }
        self._attr_native_unit_of_measurement = sensor_data.unit

        if sensor_data.type == SensorType.THROUGHPUT:
            self._attr_suggested_unit_of_measurement = (
                UnitOfDataRate.KILOBYTES_PER_SECOND
            )

    @staticmethod
    def _map_device_class(
        sensor_data: LibreHardwareMonitorSensorData,
    ) -> SensorDeviceClass | None:
        if sensor_data.type is None:
            _LOGGER.warning("Missing type for sensor: %s", sensor_data.name)
            return None

        match sensor_data.type:
            case SensorType.VOLTAGE:
                return SensorDeviceClass.VOLTAGE
            case SensorType.CURRENT:
                return SensorDeviceClass.CURRENT
            case SensorType.POWER:
                return SensorDeviceClass.POWER
            case SensorType.CLOCK | SensorType.FREQUENCY:
                return SensorDeviceClass.FREQUENCY
            case SensorType.TEMPERATURE:
                return SensorDeviceClass.TEMPERATURE
            case SensorType.FLOW:
                return SensorDeviceClass.VOLUME_FLOW_RATE
            case SensorType.FACTOR:
                return SensorDeviceClass.POWER_FACTOR
            case SensorType.DATA | SensorType.SMALL_DATA:
                return SensorDeviceClass.DATA_SIZE
            case SensorType.THROUGHPUT:
                return SensorDeviceClass.DATA_RATE
            case SensorType.TIMESPAN:
                return SensorDeviceClass.DURATION
            case SensorType.ENERGY:
                return SensorDeviceClass.ENERGY
            case SensorType.NOISE:
                return SensorDeviceClass.SOUND_PRESSURE
            case SensorType.CONDUCTIVITY:
                return SensorDeviceClass.CONDUCTIVITY
            case SensorType.HUMIDITY:
                return SensorDeviceClass.HUMIDITY
            # no matching HA sensor device classes for remaining types
            case _:
                return None

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if sensor_data := self.coordinator.data.sensor_data.get(self._sensor_id):
            self._set_state(sensor_data)
        else:
            self._attr_native_value = None

        super()._handle_coordinator_update()
