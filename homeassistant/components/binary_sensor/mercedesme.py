"""
Support for Mercedes cars with Mercedes ME.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mercedesme/
"""
import logging
import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorDevice)
from homeassistant.components.mercedesme import DATA_MME

DEPENDENCIES = ['mercedesme']

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = [
    'doorsClosed',
    'windowsClosed',
    'locked',
    'tireWarningLight'
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    if discovery_info is None:
        return

    controller = hass.data[DATA_MME]['controller']

    if not controller.cars:
        _LOGGER.error("setup_platform controller.cars is none")
        return

    devices = []
    for car in controller.cars:
        for dev in SENSOR_TYPES:
            devices.append(MercedesMEBinarySensor(dev, car, controller))

    add_devices(devices, True)


class MercedesMEBinarySensor(BinarySensorDevice):
    """Representation of a Sensor."""

    def __init__(self, sensor_name, car, controller):
        """Initialize the sensor."""
        self._state = None
        self._name = sensor_name
        self._sensor_type = None
        self._car = car
        self.controller = controller

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
                "windowStatusFrontLeft": self._car["windowStatusFrontLeft"],
                "windowStatusFrontRight": self._car["windowStatusFrontRight"],
                "windowStatusRearLeft": self._car["windowStatusRearLeft"],
                "windowStatusRearRight": self._car["windowStatusRearRight"],
                "originalValue": self._car[self._name],
                "lastUpdate": datetime.datetime.fromtimestamp(
                    self._car["lastUpdate"]).strftime('%Y-%m-%d %H:%M:%S'),
                "car": self._car["license"]
            }
        elif self._name == "tireWarningLight":
            return {
                "frontRightTirePressureKpa":
                    self._car["frontRightTirePressureKpa"],
                "frontLeftTirePressureKpa":
                    self._car["frontLeftTirePressureKpa"],
                "rearRightTirePressureKpa":
                    self._car["rearRightTirePressureKpa"],
                "rearLeftTirePressureKpa":
                    self._car["rearLeftTirePressureKpa"],
                "originalValue": self._car[self._name],
                "lastUpdate": datetime.datetime.fromtimestamp(
                    self._car["lastUpdate"]
                    ).strftime('%Y-%m-%d %H:%M:%S'),
                "car": self._car["license"]
            }
        return {
            "originalValue": self._car[self._name],
            "lastUpdate": datetime.datetime.fromtimestamp(
                self._car["lastUpdate"]).strftime('%Y-%m-%d %H:%M:%S'),
            "car": self._car["license"]
        }

    def update(self):
        """Fetch new state data for the sensor."""
        _LOGGER.debug("Updating %s", self._name)

        self.controller.update()

        if self._name == "windowsClosed":
            self._state = bool(self._car[self._name] == "CLOSED")
        elif self._name == "tireWarningLight":
            self._state = bool(self._car[self._name] != "INACTIVE")
        else:
            self._state = self._car[self._name]
