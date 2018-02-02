"""
Support for Mercedes cars with Mercedes ME.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mercedesme/
"""
import logging
import datetime

from homeassistant.components.binary_sensor import (BinarySensorDevice)
from homeassistant.components.mercedesme import (
    DATA_MME, MercedesMeEntity, BINARY_SENSORS)

DEPENDENCIES = ['mercedesme']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    data = hass.data[DATA_MME].data

    if not data.cars:
        _LOGGER.error("setup_platform data.cars is none")
        return

    devices = []
    for car in data.cars:
        for dev in BINARY_SENSORS:
            devices.append(MercedesMEBinarySensor(
                data, dev, dev, car["vin"], None))

    add_devices(devices, True)


class MercedesMEBinarySensor(MercedesMeEntity, BinarySensorDevice):
    """Representation of a Sensor."""

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state == "On"

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
                "car": self._car["license"],
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

        self._car = next(
            car for car in self._data.cars if car["vin"] == self._vin)

        result = False

        if self._name == "windowsClosed":
            result = bool(self._car[self._name] == "CLOSED")
        elif self._name == "tireWarningLight":
            result = bool(self._car[self._name] != "INACTIVE")
        else:
            result = self._car[self._name] is True

        self._state = "On" if result else "Off"

        _LOGGER.debug("Updated %s Value: %s IsOn: %s",
                      self._name, self._state, self.is_on)
