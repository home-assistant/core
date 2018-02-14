"""
Support for Mercedes cars with Mercedes ME.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.mercedesme/
"""
import logging
import datetime

from homeassistant.components.binary_sensor import (BinarySensorDevice)
from homeassistant.components.mercedesme import (
    DATA_MME, FEATURE_NOT_AVAILABLE, MercedesMeEntity, BINARY_SENSORS)

DEPENDENCIES = ['mercedesme']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    data = hass.data[DATA_MME].data

    if not data.cars:
        _LOGGER.error("No cars found. Check component log.")
        return

    devices = []
    for car in data.cars:
        for key, value in sorted(BINARY_SENSORS.items()):
            if car['availabilities'].get(key, 'INVALID') == 'VALID':
                devices.append(MercedesMEBinarySensor(
                    data, key, value[0], car["vin"], None))
            else:
                _LOGGER.warning(FEATURE_NOT_AVAILABLE, key, car["license"])

    add_devices(devices, True)


class MercedesMEBinarySensor(MercedesMeEntity, BinarySensorDevice):
    """Representation of a Sensor."""

    @property
    def is_on(self):
        """Return the state of the binary sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._internal_name == "windowsClosed":
            return {
                "window_front_left": self._car["windowStatusFrontLeft"],
                "window_front_right": self._car["windowStatusFrontRight"],
                "window_rear_left": self._car["windowStatusRearLeft"],
                "window_rear_right": self._car["windowStatusRearRight"],
                "original_value": self._car[self._internal_name],
                "last_update": datetime.datetime.fromtimestamp(
                    self._car["lastUpdate"]).strftime('%Y-%m-%d %H:%M:%S'),
                "car": self._car["license"]
            }
        elif self._internal_name == "tireWarningLight":
            return {
                "front_right_tire_pressure_kpa":
                    self._car["frontRightTirePressureKpa"],
                "front_left_tire_pressure_kpa":
                    self._car["frontLeftTirePressureKpa"],
                "rear_right_tire_pressure_kpa":
                    self._car["rearRightTirePressureKpa"],
                "rear_left_tire_pressure_kpa":
                    self._car["rearLeftTirePressureKpa"],
                "original_value": self._car[self._internal_name],
                "last_update": datetime.datetime.fromtimestamp(
                    self._car["lastUpdate"]
                    ).strftime('%Y-%m-%d %H:%M:%S'),
                "car": self._car["license"],
            }
        return {
            "original_value": self._car[self._internal_name],
            "last_update": datetime.datetime.fromtimestamp(
                self._car["lastUpdate"]).strftime('%Y-%m-%d %H:%M:%S'),
            "car": self._car["license"]
        }

    def update(self):
        """Fetch new state data for the sensor."""
        self._car = next(
            car for car in self._data.cars if car["vin"] == self._vin)

        if self._internal_name == "windowsClosed":
            self._state = bool(self._car[self._internal_name] == "CLOSED")
        elif self._internal_name == "tireWarningLight":
            self._state = bool(self._car[self._internal_name] != "INACTIVE")
        else:
            self._state = self._car[self._internal_name] is True

        _LOGGER.debug("Updated %s Value: %s IsOn: %s",
                      self._internal_name, self._state, self.is_on)
