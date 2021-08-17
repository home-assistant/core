"""Support for mill wifi-enabled home heaters."""

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR

from .const import CONSUMPTION_TODAY, CONSUMPTION_YEAR, DOMAIN, MANUFACTURER


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Mill sensor."""

    mill_data_connection = hass.data[DOMAIN]

    entities = [
        MillHeaterEnergySensor(heater, mill_data_connection, sensor_type)
        for sensor_type in (CONSUMPTION_TODAY, CONSUMPTION_YEAR)
        for heater in mill_data_connection.heaters.values()
    ]
    async_add_entities(entities)


class MillHeaterEnergySensor(SensorEntity):
    """Representation of a Mill Sensor device."""

    _attr_device_class = DEVICE_CLASS_ENERGY
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_state_class = STATE_CLASS_TOTAL_INCREASING

    def __init__(self, heater, mill_data_connection, sensor_type):
        """Initialize the sensor."""
        self._id = heater.device_id
        self._conn = mill_data_connection
        self._sensor_type = sensor_type

        self._attr_name = f"{heater.name} {sensor_type.replace('_', ' ')}"
        self._attr_unique_id = f"{heater.device_id}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, heater.device_id)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": f"generation {1 if heater.is_gen1 else 2}",
        }

    async def async_update(self):
        """Retrieve latest state."""
        heater = await self._conn.update_device(self._id)
        self._attr_available = heater.available

        if self._sensor_type == CONSUMPTION_TODAY:
            _state = heater.day_consumption
        elif self._sensor_type == CONSUMPTION_YEAR:
            _state = heater.year_consumption
        else:
            _state = None
        if _state is None:
            self._attr_native_value = _state
            return

        self._attr_native_value = _state
