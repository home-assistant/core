"""Platform for sensor integration."""
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    TEMP_CELSIUS,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util.distance import convert

from . import DOMAIN, NiuDevice


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    vehicles = hass.data[DOMAIN]["controller"].get_vehicles()

    for vehicle in vehicles:
        add_entities(
            [
                NiuSensor(vehicle, hass.data[DOMAIN]["controller"], "Level"),
                NiuSensor(vehicle, hass.data[DOMAIN]["controller"], "Level A"),
                NiuSensor(vehicle, hass.data[DOMAIN]["controller"], "Level B"),
                NiuSensor(vehicle, hass.data[DOMAIN]["controller"], "Temp A"),
                NiuSensor(vehicle, hass.data[DOMAIN]["controller"], "Temp B"),
            ]
        )


class NiuSensor(NiuDevice, Entity):
    """Representation of a Sensor."""

    def __init__(self, niu_device, controller, type=""):
        """Initialize the sensor."""
        self._niu_device = niu_device
        self._type = type

        self._unit = None
        self._icon = None
        self._state = None

        super().__init__(niu_device, controller)

    @property
    def unique_id(self) -> str:
        return f"{super().unique_id}_{self._type}"

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._niu_device.get_name()} {self._type}"

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
        return self._icon

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        super().update()

        if self._type == "Level":
            self._state = self._niu_device.get_soc()
        elif self._type == "Level A":
            self._state = self._niu_device.get_soc(0)
        elif self._type == "Level B":
            self._state = self._niu_device.get_soc(1)

        elif self._type == "Temp A":
            self._state = self._niu_device.get_battery_temp(0)
        elif self._type == "Temp B":
            self._state = self._niu_device.get_battery_temp(1)

        if "Level" in self._type:
            self._unit = "%"

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

        if "Temp" in self._type:
            self._unit = TEMP_CELSIUS

            if self._state < 15:
                self._icon = "mdi:thermometer-low"
            elif 15 <= self._state <= 40:
                self._icon = "mdi:thermometer"
            elif self._state >= 40:
                self._icon = "mdi:thermometer-high"
            else:
                self._icon = "mdi:thermometer-alert"
