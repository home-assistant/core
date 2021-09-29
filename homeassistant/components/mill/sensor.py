"""Support for mill wifi-enabled home heaters."""

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONSUMPTION_TODAY, CONSUMPTION_YEAR, DOMAIN, MANUFACTURER


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Mill sensor."""

    mill_data_coordinator = hass.data[DOMAIN]

    entities = [
        MillHeaterEnergySensor(mill_data_coordinator, sensor_type, heater)
        for sensor_type in (CONSUMPTION_TODAY, CONSUMPTION_YEAR)
        for heater in mill_data_coordinator.data.values()
    ]
    async_add_entities(entities)


class MillHeaterEnergySensor(CoordinatorEntity, SensorEntity):
    """Representation of a Mill Sensor device."""

    _attr_device_class = DEVICE_CLASS_ENERGY
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_state_class = STATE_CLASS_TOTAL_INCREASING

    def __init__(self, coordinator, sensor_type, heater):
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._id = heater.device_id
        self._sensor_type = sensor_type

        self._attr_name = f"{heater.name} {sensor_type.replace('_', ' ')}"
        self._attr_unique_id = f"{heater.device_id}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, heater.device_id)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": f"generation {1 if heater.is_gen1 else 2}",
        }
        self._update_attr(heater)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr(self.coordinator.data[self._id])
        self.async_write_ha_state()

    @callback
    def _update_attr(self, heater):
        self._attr_available = heater.available

        if self._sensor_type == CONSUMPTION_TODAY:
            self._attr_native_value = heater.day_consumption
        elif self._sensor_type == CONSUMPTION_YEAR:
            self._attr_native_value = heater.year_consumption
