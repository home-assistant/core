"""Platform for sensor integration."""
import logging

from homeassistant.const import LENGTH_KILOMETERS, PERCENTAGE, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from . import DOMAIN, NiuVehicle

_LOGGER = logging.getLogger(__name__)

# Sensors present in all vehicles
SENSORS = {
    "level": ("Battery Level", PERCENTAGE, "mdi:battery"),
    "odometer": ("Odometer", LENGTH_KILOMETERS, "mdi:counter"),
    "range": ("Range", LENGTH_KILOMETERS, "mdi:road-variant"),
    "charging time": ("Charging Time", None, "mdi:clock-outline"),
}

# Sensors present in single-battery vehicles
SENSORS_SINGLE = {
    "temp": ("Battery Temperature", TEMP_CELSIUS, "mdi:thermometer"),
}

# Sensors present in dual-battery vehicles
SENSORS_DUAL = {
    "level a": ("Battery A Level", PERCENTAGE, "mdi:battery"),
    "level b": ("Battery B Level", PERCENTAGE, "mdi:battery"),
    "temp a": ("Battery A Temperature", TEMP_CELSIUS, "mdi:thermometer"),
    "temp b": ("Battery B Temperature", TEMP_CELSIUS, "mdi:thermometer"),
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

    def __init__(self, vehicle_id, coordinator, attribute, name, unit, icon):
        """Initialize the sensor."""
        super().__init__(vehicle_id, coordinator)

        self._attribute = attribute
        self._name = name
        self._unit = unit
        self._icon = icon

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

        if "level" in self._attribute:
            if self.state < 5:
                return "mdi:battery-outline"
            if 5 <= self.state < 15:
                return "mdi:battery-10"
            if 15 <= self.state < 25:
                return "mdi:battery-20"
            if 25 <= self.state < 35:
                return "mdi:battery-30"
            if 35 <= self.state < 45:
                return "mdi:battery-40"
            if 45 <= self.state < 55:
                return "mdi:battery-50"
            if 55 <= self.state < 65:
                return "mdi:battery-60"
            if 65 <= self.state < 75:
                return "mdi:battery-70"
            if 75 <= self.state < 85:
                return "mdi:battery-80"
            if 85 <= self.state < 95:
                return "mdi:battery-90"
            if self.state >= 95:
                return "mdi:battery"

            return "mdi:battery-alert"

        if "temp" in self._attribute:
            if self._attribute == "temp b":
                desc = self._vehicle.battery_temp_desc(1)
            else:
                desc = self._vehicle.battery_temp_desc(0)

            if desc == "low":
                return "mdi:thermometer-low"
            if desc == "normal":
                return "mdi:thermometer"
            if desc == "high":
                return "mdi:thermometer-high"

            return "mdi:thermometer-alert"

        return self._icon
