"""
Support for Mercedes cars with Mercedes ME.
"""
import logging
import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDevice)

DEPENDENCIES = ['mercedesme']

DATA_MME = 'mercedesme'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    if discovery_info is None:
        return

    controller = hass.data[DATA_MME]['controller']

    if not controller.cars:
        return False

    for car in controller.cars:
        add_devices([BinarySensor('doorsClosed', car, controller)], True)
        add_devices([BinarySensor('windowsClosed', car, controller)], True)
        add_devices([BinarySensor('locked', car, controller)], True)
        add_devices([BinarySensor('tireWarningLight', car, controller)], True)

    return True


class BinarySensor(BinarySensorDevice):
    """Representation of a Sensor."""

    def __init__(self, SensorName, Car, Controller):
        """Initialize the sensor."""
        self._state = None
        self._name = SensorName
        self._sensor_type = None
        self.__car = Car
        self.controller = Controller

    @property
    def device_class(self):
        """Return the class of this binary sensor."""
        return self._sensor_type

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._name == "windowsClosed":
            return {
                "windowStatusFrontLeft": self.__car["windowStatusFrontLeft"],
                "windowStatusFrontRight": self.__car["windowStatusFrontRight"],
                "windowStatusRearLeft": self.__car["windowStatusRearLeft"],
                "windowStatusRearRight": self.__car["windowStatusRearRight"],
                "originalValue": self.__car[self._name],
                "lastUpdate": datetime.datetime.fromtimestamp(
                    self.__car["lastUpdate"]).strftime('%Y-%m-%d %H:%M:%S'),
                "car": self.__car["license"]
            }
        elif self._name == "tireWarningLight":
            return {
                "frontRightTirePressureKpa":
                    self.__car["frontRightTirePressureKpa"],
                "frontLeftTirePressureKpa":
                    self.__car["frontLeftTirePressureKpa"],
                "rearRightTirePressureKpa":
                    self.__car["rearRightTirePressureKpa"],
                "rearLeftTirePressureKpa":
                    self.__car["rearLeftTirePressureKpa"],
                "originalValue": self.__car[self._name],
                "lastUpdate": datetime.datetime.fromtimestamp(
                    self.__car["lastUpdate"]
                    ).strftime('%Y-%m-%d %H:%M:%S'),
                "car": self.__car["license"]
            }
        return {
            "originalValue": self.__car[self._name],
            "lastUpdate": datetime.datetime.fromtimestamp(
                self.__car["lastUpdate"]).strftime('%Y-%m-%d %H:%M:%S'),
            "car": self.__car["license"]
        }

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self.controller.update()

        if self._name == "windowsClosed":
            self._state = bool(self.__car[self._name] == "CLOSED")
        elif self._name == "tireWarningLight":
            self._state = bool(self.__car[self._name] != "INACTIVE")
        else:
            self._state = self.__car[self._name]
