"""
Support for Mercedes cars with Mercedes ME.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mercedesme/
"""
import logging
import datetime

from homeassistant.const import LENGTH_KILOMETERS
from homeassistant.components.mercedesme import DATA_MME, MercedesMeEntity


DEPENDENCIES = ['mercedesme']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    'fuelLevelPercent': ['Fuel Level', '%'],
    'fuelRangeKm': ['Fuel Range', LENGTH_KILOMETERS],
    'latestTrip': ['Latest Trip', None],
    'odometerKm': ['Odometer', LENGTH_KILOMETERS],
    'serviceIntervalDays': ['Next Service', 'days'],
    'doorsClosed': ['doorsClosed', None],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    if discovery_info is None:
        return

    data = hass.data[DATA_MME].data

    if not data.cars:
        return

    devices = []
    for car in data.cars:
        for key, value in sorted(SENSOR_TYPES.items()):
            devices.append(
                MercedesMESensor(data, key, value[0], car["vin"], value[1]))

    add_devices(devices, True)


class MercedesMESensor(MercedesMeEntity):
    """Representation of a Sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating %s", self._internal_name)

        self._car = next(
            car for car in self._data.cars if car["vin"] == self._vin)

        if self._internal_name == "latestTrip":
            self._state = self._car["latestTrip"]["id"]
        else:
            self._state = self._car[self._internal_name]

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
