"""Support for LibreHardwareMonitor Sensor Platform."""

from collections.abc import Mapping
import logging
from typing import Any, override

from librehardwaremonitor_api.model import LibreHardwareMonitorSensorData
from librehardwaremonitor_api.sensor_type import SensorType

from homeassistant.components.sensor import (
    AMBIGUOUS_UNITS,
    UNIT_CONVERTERS,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, UnitOfInformation
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LibreHardwareMonitorConfigEntry, LibreHardwareMonitorCoordinator
from .const import DOMAIN, LEGACY_DATA_SIZE_UNIT_EQUIVALENTS

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

STATE_MIN_VALUE = "min_value"
STATE_MAX_VALUE = "max_value"

# Remove sensors which are missing for this amount of successful consecutive updates
# 1 minute at the default interval of 10 seconds
MISSING_SENSOR_REMOVAL_UPDATES = 6

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
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    unique_id_prefix = f"{config_entry.entry_id}_"

    added_sensor_ids: set[str] = set()
    missing_from_updates: dict[str, int] = {}

    @callback
    def _async_remove_sensor(sensor_id: str, entity_id: str) -> None:
        missing_from_updates.pop(sensor_id, None)
        added_sensor_ids.discard(sensor_id)
        entity_registry.async_remove(entity_id)

    @callback
    def _async_remove_replaced_sensor(
        sensor_data: Mapping[str, LibreHardwareMonitorSensorData],
        new_sensor: LibreHardwareMonitorSensorData,
    ) -> None:
        """Remove a sensor that is replaced by a new sensor id to preserve the entity id.

        LHM updates can change sensor ids, e.g. when a sensor moves to another
        index. The replaced sensor has the same name on the same device and is no
        longer reported by LHM.
        """
        if not (
            device := device_registry.async_get_device_by_identifier(
                (DOMAIN, f"{unique_id_prefix}{new_sensor.device_id}"),
                config_entry.entry_id,
            )
        ):
            return

        for registry_entry in er.async_entries_for_device(
            entity_registry, device.id, include_disabled_entities=True
        ):
            replaced_sensor_id = registry_entry.unique_id.removeprefix(unique_id_prefix)
            if (
                registry_entry.original_name != new_sensor.name
                or replaced_sensor_id in sensor_data
            ):
                continue

            _LOGGER.debug(
                "Sensor %s replaces %s, removing it",
                new_sensor.sensor_id,
                replaced_sensor_id,
            )
            _async_remove_sensor(replaced_sensor_id, registry_entry.entity_id)

    @callback
    def _async_handle_sensor_changes() -> None:
        if not lhm_coordinator.last_update_success:
            return

        sensor_data = lhm_coordinator.data.sensor_data

        if new_sensor_ids := [
            sensor_id for sensor_id in sensor_data if sensor_id not in added_sensor_ids
        ]:
            for sensor_id in new_sensor_ids:
                _LOGGER.debug("New sensor detected, adding: %s", sensor_id)
                _async_remove_replaced_sensor(sensor_data, sensor_data[sensor_id])
            added_sensor_ids.update(new_sensor_ids)
            async_add_entities(
                LibreHardwareMonitorSensor(
                    lhm_coordinator, config_entry.entry_id, sensor_data[sensor_id]
                )
                for sensor_id in new_sensor_ids
            )

        # Check if we have a registered entity that is no longer reported by LHM
        registry_entries = {
            entry.unique_id.removeprefix(unique_id_prefix): entry
            for entry in er.async_entries_for_config_entry(
                entity_registry, config_entry.entry_id
            )
        }
        for sensor_id, registry_entry in registry_entries.items():
            if sensor_id in sensor_data:
                missing_from_updates.pop(sensor_id, None)
                continue

            missing_from_updates[sensor_id] = missing_from_updates.get(sensor_id, 0) + 1
            if missing_from_updates[sensor_id] < MISSING_SENSOR_REMOVAL_UPDATES:
                continue

            _LOGGER.debug("Sensor %s no longer available, removing", sensor_id)
            _async_remove_sensor(sensor_id, registry_entry.entity_id)

        # Check if we have a registered device that no longer holds any sensors
        # and if so, remove it
        for device in dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        ):
            if er.async_entries_for_device(
                entity_registry, device.id, include_disabled_entities=True
            ):
                continue

            _LOGGER.warning("Device %s no longer available, removing", device.name)
            device_registry.async_remove_device(device.id)

    _async_handle_sensor_changes()
    config_entry.async_on_unload(
        lhm_coordinator.async_add_listener(_async_handle_sensor_changes)
    )


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
            elif device_class is SensorDeviceClass.DATA_SIZE:
                # LHM versions >= 0.9.7 report data sizes in raw bytes
                self._attr_suggested_unit_of_measurement = UnitOfInformation.GIBIBYTES

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
        # This conversion is only needed for LHM versions < 0.9.7
        self._attr_native_unit_of_measurement = (
            LEGACY_DATA_SIZE_UNIT_EQUIVALENTS.get(sensor_data.unit, sensor_data.unit)
            if sensor_data.type in (SensorType.DATA, SensorType.SMALL_DATA)
            else sensor_data.unit
        )
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
        # Conductivity uses micro-sign U+00B5 spelling in its unit which cannot be converted
        # so we swap it with Greek mu U+03BC to get μS/cm as a valid unit
        native_unit = AMBIGUOUS_UNITS.get(
            self.native_unit_of_measurement, self.native_unit_of_measurement
        )
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
