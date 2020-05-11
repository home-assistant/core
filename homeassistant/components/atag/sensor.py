"""Initialization of ATAG One sensor platform."""
from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from . import DOMAIN, AtagEntity

SENSORS = [
    "Burning Hours",
    "Outside Temperature",
    "Flame",
    "Average Outside Temperature",
    "Weather Status",
    "CH Return Temperature",
    "CH Water Pressure",
    "CH Water Temperature",
]


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
        self.coordinator = coordinator
        self._id = sensor
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
