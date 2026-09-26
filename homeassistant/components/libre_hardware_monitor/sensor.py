"""Support for LibreHardwareMonitor Sensor Platform."""

import logging
from typing import Any, override

from librehardwaremonitor_api.model import DeviceId, LibreHardwareMonitorSensorData
from librehardwaremonitor_api.sensor_type import SensorType

from homeassistant.components.sensor import (
    UNIT_CONVERTERS,
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

DEVICE_CLASSES: dict[SensorType, SensorDeviceClass] = {
    SensorType.VOLTAGE: SensorDeviceClass.VOLTAGE,
    SensorType.CURRENT: SensorDeviceClass.CURRENT,
    SensorType.POWER: SensorDeviceClass.POWER,
    SensorType.CLOCK: SensorDeviceClass.FREQUENCY,
    SensorType.FREQUENCY: SensorDeviceClass.FREQUENCY,
    SensorType.TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    SensorType.FLOW: SensorDeviceClass.VOLUME_FLOW_RATE,
    SensorType.DATA: SensorDeviceClass.DATA_SIZE,
    SensorType.SMALL_DATA: SensorDeviceClass.DATA_SIZE,
    SensorType.THROUGHPUT: SensorDeviceClass.DATA_RATE,
    SensorType.TIMESPAN: SensorDeviceClass.DURATION,
    SensorType.ENERGY: SensorDeviceClass.ENERGY_STORAGE,
    SensorType.NOISE: SensorDeviceClass.SOUND_PRESSURE,
    SensorType.CONDUCTIVITY: SensorDeviceClass.CONDUCTIVITY,
    SensorType.HUMIDITY: SensorDeviceClass.HUMIDITY,
}


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

        if sensor_data.type is None:
            _LOGGER.debug("Missing type for sensor: %s", sensor_data.name)
        elif device_class := DEVICE_CLASSES.get(sensor_data.type):
            self._attr_device_class = device_class

            if device_class is SensorDeviceClass.DATA_RATE:
                self._attr_suggested_unit_of_measurement = (
                    UnitOfDataRate.KIBIBYTES_PER_SECOND
                )
                # Device class default rounds throughput to whole KiB/s
                self._attr_suggested_display_precision = 1
            elif device_class is SensorDeviceClass.VOLTAGE:
                # Device class default rounds voltages to whole volts
                self._attr_suggested_display_precision = 3

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
        self._attr_native_unit_of_measurement = sensor_data.unit
        self._native_min_value = sensor_data.min
        self._native_max_value = sensor_data.max

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return min and max values in the unit the state is reported in."""
        return {
            STATE_MIN_VALUE: self._value_in_state_unit(self._native_min_value),
            STATE_MAX_VALUE: self._value_in_state_unit(self._native_max_value),
        }

    def _value_in_state_unit(self, native_value: str | None) -> str | float | None:
        """Convert a native value to the unit the state is converted to."""
        native_unit = self.native_unit_of_measurement
        unit = self.unit_of_measurement
        if (
            native_value is None
            or native_unit == unit
            or (converter := UNIT_CONVERTERS.get(self.device_class)) is None
            or native_unit not in converter.VALID_UNITS
            or unit not in converter.VALID_UNITS
        ):
            return native_value

        return converter.convert(float(native_value), native_unit, unit)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if sensor_data := self.coordinator.data.sensor_data.get(self._sensor_id):
            self._set_state(sensor_data)
        else:
            self._attr_native_value = None

        super()._handle_coordinator_update()
