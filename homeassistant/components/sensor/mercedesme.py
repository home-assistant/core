"""
Support for Mercedes cars with Mercedes ME.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mercedesme/
"""
import logging
import datetime

from homeassistant.const import LENGTH_KILOMETERS
from homeassistant.components.mercedesme import DATA_MME
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['mercedesme']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'fuelLevelPercent': ['Fuel Level', '%'],
    'fuelRangeKm': ['Fuel Range', LENGTH_KILOMETERS],
    'latestTrip': ['Latest Trip', None],
    'odometerKm': ['Odometer', LENGTH_KILOMETERS],
    'serviceIntervalDays': ['Next Service', 'days'],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    if discovery_info is None:
        return

    controller = hass.data[DATA_MME]['controller']

    if not controller.cars:
        return

    devices = []
    for car in controller.cars:
        for key, value in sorted(SENSOR_TYPES.items()):
            devices.append(
                MercedesMESensor(key, value[0], car, controller, value[1]))

    add_devices(devices, True)


class MercedesMESensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, internal_name, sensor_name, car, controller, unit):
        """Initialize the sensor."""
        self._state = None
        self._name = sensor_name
        self._internal_name = internal_name
        self._car = car
        self.controller = controller
        self._unit = unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._internal_name == "latestTrip":
            return {
                "durationSeconds":
                    self._car["latestTrip"]["durationSeconds"],
                "distanceTraveledKm":
                    self._car["latestTrip"]["distanceTraveledKm"],
                "startedAt": datetime.datetime.fromtimestamp(
                    self._car["latestTrip"]["startedAt"]
                    ).strftime('%Y-%m-%d %H:%M:%S'),
                "averageSpeedKmPerHr":
                    self._car["latestTrip"]["averageSpeedKmPerHr"],
                "finished": self._car["latestTrip"]["finished"],
                "lastUpdate": datetime.datetime.fromtimestamp(
                    self._car["lastUpdate"]
                    ).strftime('%Y-%m-%d %H:%M:%S'),
                "car": self._car["license"]
            }

        return {
            "lastUpdate": datetime.datetime.fromtimestamp(
                self._car["lastUpdate"]).strftime('%Y-%m-%d %H:%M:%S'),
            "car": self._car["license"]
        }

    def update(self):
        """Fetch new state data for the sensor."""
        _LOGGER.debug("Updating %s", self._internal_name)

        self.controller.update()

        if self._internal_name == "latestTrip":
            self._state = self._car["latestTrip"]["id"]
        else:
            self._state = self._car[self._internal_name]
