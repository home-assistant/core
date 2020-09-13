"""Platform for sensor integration."""
import logging

from homeassistant.const import (ATTR_BATTERY_CHARGING, ATTR_BATTERY_LEVEL,
                                 LENGTH_KILOMETERS, PERCENTAGE, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity

from . import DOMAIN

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

    await hass.data[DOMAIN][config.entry_id]["account"].update_vehicles()
    for vehicle in hass.data[DOMAIN][config.entry_id]["account"].get_vehicles():
        entities = []

        for key, value in SENSORS.items():
            entities.append(
                NiuSensor(hass.data[DOMAIN], vehicle, key, value[0], value[1], value[2])
            )

        for key, value in (
            SENSORS_SINGLE.items()
            if vehicle.get_battery_count() == 1
            else SENSORS_DUAL.items()
        ):
            entities.append(
                NiuSensor(hass.data[DOMAIN], vehicle, key, value[0], value[1], value[2])
            )

        add_entities(entities, True)


class NiuSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, account, vehicle, attribute, name, unit, icon):
        """Initialize the sensor."""
        self._account = account
        self._serial = vehicle.get_serial()
        self._vehicle = vehicle
        self._attribute = attribute
        self._name = name

        self._unit = unit
        self._icon = icon
        self._state = None

    @property
    def unique_id(self) -> str:
        """Return the unique id for the sensor."""
        return f"{self._serial}_{self._attribute}"

    @property
    def should_poll(self) -> bool:
        """Return false since data update is centralized in NiuAccount."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._vehicle.get_name()} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_BATTERY_LEVEL: self._vehicle.get_soc(),
            ATTR_BATTERY_CHARGING: self._vehicle.is_charging(),
        }

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": (DOMAIN, self._serial),
            "name": self._vehicle.get_name(),
            "manufacturer": "NIU",
            "model": self._vehicle.get_model(),
            "sw_version": self._vehicle.get_firmware(),
        }

    def update_callback(self):
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register state update callback."""

        self._account.add_update_listener(self.update_callback)

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        self._vehicle = next(
            (
                veh
                for veh in self._account.get_vehicles()
                if veh.get_serial() == self._serial
            ),
            None,
        )

        if self._vehicle is None:
            _LOGGER.error("Scooter %s has been removed from the cloud", self._serial)

        _LOGGER.debug("Updating %s", self.name)

        # Odometer
        if self._attribute == "odometer":
            self._state = self._vehicle.get_odometer()

        # Range
        if self._attribute == "range":
            self._state = self._vehicle.get_range()

        # Charging time
        if self._attribute == "charging time":
            self._state = self._vehicle.get_charging_left()

        # Temperature
        desc = ""
        if self._attribute == "temp" or self._attribute == "temp a":
            self._state = self._vehicle.get_battery_temp(0)
            desc = self._vehicle.get_battery_temp_desc(0)
        if self._attribute == "temp b":
            self._state = self._vehicle.get_battery_temp(1)
            desc = self._vehicle.get_battery_temp_desc(1)

        if "temp" in self._attribute:
            if desc == "low":
                self._icon = "mdi:thermometer-low"
            elif desc == "normal":
                self._icon = "mdi:thermometer"
            elif desc == "high":
                self._icon = "mdi:thermometer-high"
            else:
                self._icon = "mdi:thermometer-alert"

        # Battery level
        if self._attribute == "level":
            self._state = self._vehicle.get_soc()
        if self._attribute == "level a":
            self._state = self._vehicle.get_soc(0)
        if self._attribute == "level b":
            self._state = self._vehicle.get_soc(1)

        if "level" in self._attribute:
            if self._state < 5:
                self._icon = "mdi:battery-outline"
            elif 5 <= self._state < 15:
                self._icon = "mdi:battery-10"
            elif 15 <= self._state < 25:
                self._icon = "mdi:battery-20"
            elif 25 <= self._state < 35:
                self._icon = "mdi:battery-30"
            elif 35 <= self._state < 45:
                self._icon = "mdi:battery-40"
            elif 45 <= self._state < 55:
                self._icon = "mdi:battery-50"
            elif 55 <= self._state < 65:
                self._icon = "mdi:battery-60"
            elif 65 <= self._state < 75:
                self._icon = "mdi:battery-70"
            elif 75 <= self._state < 85:
                self._icon = "mdi:battery-80"
            elif 85 <= self._state < 95:
                self._icon = "mdi:battery-90"
            elif self._state >= 95:
                self._icon = "mdi:battery"
            else:
                self._icon = "mdi:battery-alert"
