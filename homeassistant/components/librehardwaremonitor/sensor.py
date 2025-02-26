"""Support for LibreHardwareMonitor Sensor Platform."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

STATE_MIN_VALUE = "min_value"
STATE_MAX_VALUE = "max_value"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LibreHardwareMonitor platform."""
    lhm_coordinator = config_entry.runtime_data

    sensor_entities = [
        LibreHardwareMonitorSensor(lhm_coordinator, sensor_data)
        for sensor_data in lhm_coordinator.data.values()
    ]

    async_add_entities(sensor_entities)


class LibreHardwareMonitorSensor(CoordinatorEntity, SensorEntity):
    """Sensor to display information from LibreHardwareMonitor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(self, coordinator, sensor_data):
        """Initialize an LibreHardwareMonitor sensor."""
        super().__init__(coordinator)

        self._coordinator = coordinator

        self._attr_name = sensor_data.name
        self.value = sensor_data.value
        self.attributes = {
            STATE_MIN_VALUE: self._format_number_value(sensor_data.min),
            STATE_MAX_VALUE: self._format_number_value(sensor_data.max),
        }
        self._unit_of_measurement = sensor_data.unit
        self._attr_unique_id = f"lhm-{sensor_data.sensor_id}"

        self._sensor_id = sensor_data.sensor_id

        # Hardware device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sensor_data.device_name)},
            name=sensor_data.device_name,
            manufacturer="Hardware",
            model=sensor_data.device_type,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if sensor_data := self._coordinator.data.get(self._sensor_id):
            self.value = sensor_data.value
            self.attributes = {
                STATE_MIN_VALUE: self._format_number_value(sensor_data.min),
                STATE_MAX_VALUE: self._format_number_value(sensor_data.max),
            }
        else:
            self.value = None

        self.async_write_ha_state()

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def native_value(self):
        """Return the state of the device."""
        if self.value is not None and self.value != "-":
            return self._format_number_value(self.value)
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the entity."""
        return self.attributes

    @staticmethod
    def _format_number_value(number_str) -> str:
        return number_str.replace(",", ".")
