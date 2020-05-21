"""Initialization of ATAG One sensor platform."""
from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
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
    entities = []
    for sensor in SENSORS:
        entities.append(AtagSensor(coordinator, sensor))
    async_add_entities(entities)


class AtagSensor(AtagEntity):
    """Representation of a AtagOne Sensor."""

    def __init__(self, coordinator, sensor):
        """Initialize Atag sensor."""
        super().__init__(coordinator, SENSORS[sensor])
        self._name = sensor

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._id].state

    @property
    def icon(self):
        """Return icon."""
        return self.coordinator.data[self._id].icon

    @property
    def device_class(self):
        """Return deviceclass."""
        if self.coordinator.data[self._id].sensorclass in [
            DEVICE_CLASS_PRESSURE,
            DEVICE_CLASS_TEMPERATURE,
        ]:
            return self.coordinator.data[self._id].sensorclass
        return None

    @property
    def unit_of_measurement(self):
        """Return measure."""
        if self.coordinator.data[self._id].measure in [
            PRESSURE_BAR,
            TEMP_CELSIUS,
            TEMP_FAHRENHEIT,
        ]:
            return self.coordinator.data[self._id].measure
        return None
