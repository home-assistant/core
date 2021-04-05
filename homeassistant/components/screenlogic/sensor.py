"""Support for a ScreenLogic Sensor."""
import logging

from screenlogicpy.const import DEVICE_TYPE

from homeassistant.components.sensor import (
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    SensorEntity,
)

from . import ScreenlogicEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PUMP_SENSORS = ("currentWatts", "currentRPM", "currentGPM")

SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS = {
    DEVICE_TYPE.TEMPERATURE: DEVICE_CLASS_TEMPERATURE,
    DEVICE_TYPE.ENERGY: DEVICE_CLASS_POWER,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]
    # Generic sensors
    for sensor in data["devices"]["sensor"]:
        entities.append(ScreenLogicSensor(coordinator, sensor))
    # Pump sensors
    for pump in data["devices"]["pump"]:
        for pump_key in PUMP_SENSORS:
            entities.append(ScreenLogicPumpSensor(coordinator, pump, pump_key))

    async_add_entities(entities)


class ScreenLogicSensor(ScreenlogicEntity, SensorEntity):
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
        device_class = self.sensor.get("device_type")
        return SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(device_class)

    @property
    def state(self):
        """State of the sensor."""
        value = self.sensor["value"]
        return (value - 1) if "supply" in self._data_key else value

    @property
    def sensor(self):
        """Shortcut to access the sensor data."""
        return self.coordinator.data["sensors"][self._data_key]


class ScreenLogicPumpSensor(ScreenlogicEntity, SensorEntity):
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
        device_class = self.pump_sensor.get("device_type")
        return SL_DEVICE_TYPE_TO_HA_DEVICE_CLASS.get(device_class)

    @property
    def state(self):
        """State of the pump sensor."""
        return self.pump_sensor["value"]

    @property
    def pump_sensor(self):
        """Shortcut to access the pump sensor data."""
        return self.coordinator.data["pumps"][self._pump_id][self._key]
