"""Platform for sensor integration."""
import logging

from homeassistant.components.sensor import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.const import LENGTH_KILOMETERS, PERCENTAGE, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from . import NiuVehicle
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Sensors present in all vehicles
SENSORS = {
    "level": ("Battery Level", PERCENTAGE, DEVICE_CLASS_BATTERY),
    "odometer": ("Odometer", LENGTH_KILOMETERS, None),
    "range": ("Range", LENGTH_KILOMETERS, None),
    "charging time": ("Charging Time", None, None),
}

# Sensors present in single-battery vehicles
SENSORS_SINGLE = {
    "temp": ("Battery Temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE),
}

# Sensors present in dual-battery vehicles
SENSORS_DUAL = {
    "level a": ("Battery A Level", PERCENTAGE, DEVICE_CLASS_BATTERY),
    "level b": ("Battery B Level", PERCENTAGE, DEVICE_CLASS_BATTERY),
    "temp a": ("Battery A Temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE),
    "temp b": ("Battery B Temperature", TEMP_CELSIUS, DEVICE_CLASS_TEMPERATURE),
}


async def async_setup_entry(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    coord = hass.data[DOMAIN][config.entry_id]["coordinator"]

    for serial, vehicle in (
        hass.data[DOMAIN][config.entry_id]["account"].get_vehicles().items()
    ):
        entities = []

        for key, value in SENSORS.items():
            entities.append(NiuSensor(serial, coord, key, value[0], value[1], value[2]))

        for key, value in (
            SENSORS_SINGLE.items()
            if vehicle.battery_count == 1
            else SENSORS_DUAL.items()
        ):
            entities.append(NiuSensor(serial, coord, key, value[0], value[1], value[2]))

        add_entities(entities, True)


class NiuSensor(NiuVehicle, Entity):
    """Representation of a Sensor."""

    def __init__(self, vehicle_id, coordinator, attribute, name, unit, device_class):
        """Initialize the sensor."""
        super().__init__(vehicle_id, device_class, coordinator)

        self._attribute = attribute
        self._name = name
        self._unit = unit

    @property
    def unique_id(self) -> str:
        """Return the unique id for the sensor."""
        return f"{self._vehicle.serial_number}_{self._attribute}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._vehicle.name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""

        # Battery level
        if self._attribute == "level":
            return self._vehicle.soc()
        if self._attribute == "level a":
            return self._vehicle.soc(0)
        if self._attribute == "level b":
            return self._vehicle.soc(1)

        # Odometer
        if self._attribute == "odometer":
            return self._vehicle.odometer

        # Range
        if self._attribute == "range":
            return self._vehicle.range

        # Charging time
        if self._attribute == "charging time":
            return self._vehicle.charging_time_left

        # Temperature
        if self._attribute == "temp" or self._attribute == "temp a":
            return self._vehicle.battery_temp(0)
        if self._attribute == "temp b":
            return self._vehicle.battery_temp(1)

        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon of the sensor."""

        if not self.device_class:
            if self._attribute == "range":
                return "mdi:road-variant"
            if self._attribute == "odometer":
                return "mdi:counter"
            if self._attribute == "charging time":
                return "mdi:clock-outline"

        return None
