"""Support for a ScreenLogic Sensor."""
import logging

from homeassistant.components.sensor import DEVICE_CLASSES

from . import ScreenlogicEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PUMP_SENSORS = ("currentWatts", "currentRPM", "currentGPM")


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    # Generic sensors
    for sensor in data["devices"]["sensor"]:
        entities.append(ScreenLogicSensor(coordinator, sensor))
    for pump in data["devices"]["pump"]:
        for pump_key in PUMP_SENSORS:
            entities.append(ScreenLogicPumpSensor(coordinator, pump, pump_key))

    async_add_entities(entities, True)


class ScreenLogicSensor(ScreenlogicEntity):
    """Representation of a ScreenLogic sensor entity."""

    @property
    def name(self):
        """Name of the sensor."""
        return f"{self.gateway_name} {self.sensor['name']}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.sensor.get("unit")

    @property
    def device_class(self):
        """Device class of the sensor."""
        device_class = self.sensor.get("hass_type")
        if device_class in DEVICE_CLASSES:
            return device_class
        return None

    @property
    def state(self):
        """State of the sensor."""
        value = self.sensor["value"]
        return (value - 1) if "supply" in self._data_key else value

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.sensor_data[self._data_key]

    @property
    def sensor_data(self):
        """Shortcut to access the sensors data."""
        return self.coordinator.data["sensors"]


class ScreenLogicPumpSensor(ScreenlogicEntity):
    """Representation of a ScreenLogic pump sensor entity."""

    def __init__(self, coordinator, pump, key):
        """Initialize of the pump sensor."""
        super().__init__(coordinator, f"{key}_{pump}")
        self._pump_id = pump
        self._key = key

    @property
    def name(self):
        """Return the pump sensor name."""
        return f"{self.gateway_name} {self.pump_sensor['name']}"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.pump_sensor.get("unit")

    @property
    def device_class(self):
        """Return the device class."""
        device_class = self.pump_sensor.get("hass_type")
        if device_class in DEVICE_CLASSES:
            return device_class
        return None

    @property
    def state(self):
        """State of the pump sensor."""
        return self.pump_sensor["value"]

    @property
    def pump_sensor(self):
        """Shortcut to access the pump sensor data."""
        return self.pumps_data[self._pump_id][self._key]

    @property
    def pumps_data(self):
        """Shortcut to access the pump data."""
        return self.coordinator.data["pumps"]
