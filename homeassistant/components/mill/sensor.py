"""Support for mill wifi-enabled home heaters."""

from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, STATE_UNKNOWN
from homeassistant.util import dt as dt_util

from .const import CONSUMPTION_TODAY, CONSUMPTION_YEAR, DOMAIN, MANUFACTURER


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Mill sensor."""

    mill_data_connection = hass.data[DOMAIN]

    dev = []
    for heater in mill_data_connection.heaters.values():
        for sensor_type in (CONSUMPTION_TODAY, CONSUMPTION_YEAR):
            dev.append(
                MillHeaterEnergySensor(heater, mill_data_connection, sensor_type)
            )
    async_add_entities(dev)


class MillHeaterEnergySensor(SensorEntity):
    """Representation of a Mill Sensor device."""

    def __init__(self, heater, mill_data_connection, sensor_type):
        """Initialize the sensor."""
        self._id = heater.device_id
        self._conn = mill_data_connection
        self._sensor_type = sensor_type

        self._attr_device_class = DEVICE_CLASS_ENERGY
        self._attr_name = f"{heater.name} {sensor_type.replace('_', ' ')}"
        self._attr_unique_id = f"{heater.device_id}_{sensor_type}"
        self._attr_unit_of_measurement = ENERGY_KILO_WATT_HOUR
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_device_info = {
            "identifiers": {(DOMAIN, heater.device_id)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": f"generation {1 if heater.is_gen1 else 2}",
        }
        if self._sensor_type == CONSUMPTION_TODAY:
            self._attr_last_reset = dt_util.as_utc(
                dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
            )
        elif self._sensor_type == CONSUMPTION_YEAR:
            self._attr_last_reset = dt_util.as_utc(
                dt_util.now().replace(
                    month=1, day=1, hour=0, minute=0, second=0, microsecond=0
                )
            )

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
            self._attr_state = _state
            return

        if self.state not in [STATE_UNKNOWN, None] and _state < self.state:
            if self._sensor_type == CONSUMPTION_TODAY:
                self._attr_last_reset = dt_util.as_utc(
                    dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
                )
            elif self._sensor_type == CONSUMPTION_YEAR:
                self._attr_last_reset = dt_util.as_utc(
                    dt_util.now().replace(
                        month=1, day=1, hour=0, minute=0, second=0, microsecond=0
                    )
                )
        self._attr_state = _state
