"""Support for LibreHardwareMonitor Sensor Platform."""

from __future__ import annotations

from librehardwaremonitor_api.model import LibreHardwareMonitorSensorData

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LibreHardwareMonitorConfigEntry, LibreHardwareMonitorCoordinator
from .const import DOMAIN

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

    async_add_entities(
        LibreHardwareMonitorSensor(lhm_coordinator, config_entry.entry_id, sensor_data)
        for sensor_data in lhm_coordinator.data.sensor_data.values()
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
        self.value: str | None = sensor_data.value
        self._attr_extra_state_attributes: dict[str, str] = {
            STATE_MIN_VALUE: self._format_number_value(sensor_data.min),
            STATE_MAX_VALUE: self._format_number_value(sensor_data.max),
        }
        self._attr_native_unit_of_measurement = sensor_data.unit
        self._attr_unique_id: str = f"{entry_id}_{sensor_data.sensor_id}"

        self._sensor_id: str = sensor_data.sensor_id

        # Hardware device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{sensor_data.device_id}")},
            name=sensor_data.device_name,
            model=sensor_data.device_type,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if sensor_data := self.coordinator.data.sensor_data.get(self._sensor_id):
            self.value = sensor_data.value
            self._attr_extra_state_attributes = {
                STATE_MIN_VALUE: self._format_number_value(sensor_data.min),
                STATE_MAX_VALUE: self._format_number_value(sensor_data.max),
            }
        else:
            self.value = None

        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Return the formatted sensor value or None if no value is available."""
        if self.value is not None and self.value != "-":
            return self._format_number_value(self.value)
        return None

    @staticmethod
    def _format_number_value(number_str: str) -> str:
        return number_str.replace(",", ".")
