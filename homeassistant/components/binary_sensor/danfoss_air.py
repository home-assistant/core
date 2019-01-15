"""
Binary sensors for Danfoss Air HRV.

Configuration:
    danfoss_air:
        host: IP_OF_CCM_MODULE

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.danfoss_air/
"""
from homeassistant.components.binary_sensor import (
     BinarySensorDevice)

SENSORS = {
        'bypass_active': ["Danfoss Air Bypass Active", 'BYPASS_ACTIVE']
        }


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the available Danfoss Air sensors etc."""
    data = hass.data["DANFOSS_DO"]

    dev = []

    for key in SENSORS.keys():
        dev.append(DanfossAirBinarySensor(data, SENSORS[key][0],
                                          SENSORS[key][1]))

    add_devices(dev, True)


class DanfossAirBinarySensor(BinarySensorDevice):
    """Representation of a Danfoss Air binary sensor."""

    def __init__(self, data, name, sensor_type):
        """Initialize the Danfoss Air binary sensor."""
        self._data = data
        self._name = name
        self._state = None
        self._type = sensor_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Type of device class."""
        return "opening"

    def update(self):
        """Fetch new state data for the sensor."""
        self._data.update()

        self._state = self._data.getValue(self._type)
