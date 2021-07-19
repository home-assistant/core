"""Initialization of ATAG One sensor platform."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
)

from . import DOMAIN, AtagEntity

SENSORS = {
    "Outside Temperature": "outside_temp",
    "Average Outside Temperature": "tout_avg",
    "Weather Status": "weather_status",
    "CH Water Pressure": "ch_water_pres",
    "CH Water Temperature": "ch_water_temp",
    "CH Return Temperature": "ch_return_temp",
    "Burning Hours": "burning_hours",
    "Flame": "rel_mod_level",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Initialize sensor platform from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([AtagSensor(coordinator, sensor) for sensor in SENSORS])


class AtagSensor(AtagEntity, SensorEntity):
    """Representation of a AtagOne Sensor."""

    def __init__(self, coordinator, sensor):
        """Initialize Atag sensor."""
        super().__init__(coordinator, SENSORS[sensor])
        self._attr_name = sensor
        if coordinator.data.report[self._id].sensorclass in [
            DEVICE_CLASS_PRESSURE,
            DEVICE_CLASS_TEMPERATURE,
        ]:
            self._attr_device_class = coordinator.data.report[self._id].sensorclass
        if coordinator.data.report[self._id].measure in [
            PRESSURE_BAR,
            TEMP_CELSIUS,
            TEMP_FAHRENHEIT,
            PERCENTAGE,
            TIME_HOURS,
        ]:
            self._attr_unit_of_measurement = coordinator.data.report[self._id].measure

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data.report[self._id].state

    @property
    def icon(self):
        """Return icon."""
        return self.coordinator.data.report[self._id].icon
