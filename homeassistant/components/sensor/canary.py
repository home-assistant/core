"""
Support for Canary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.canary/
"""

from canary.api import SensorType

from homeassistant.components.canary import DATA_CANARY
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['canary']

SENSOR_VALUE_PRECISION = 2
ATTR_AIR_QUALITY_READING = "air_quality_reading"

# Sensor types are defined like so:
# SensorType enum, unit_of_measurement, icon
SENSOR_TYPES = [
    [SensorType.TEMPERATURE, TEMP_CELSIUS, "mdi:thermometer"],
    [SensorType.HUMIDITY, "%", "mdi:water-percent"],
    [SensorType.AIR_QUALITY, None, "mdi:weather-windy"],
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Canary sensors."""
    data = hass.data[DATA_CANARY]
    devices = []

    for location in data.locations:
        for device in location.devices:
            if device.is_online:
                for sensor_type in SENSOR_TYPES:
                    devices.append(CanarySensor(data, sensor_type, location,
                                                device))

    add_devices(devices, True)


class CanarySensor(Entity):
    """Representation of a Canary sensor."""

    def __init__(self, data, sensor_type, location, device):
        """Initialize the sensor."""
        self._data = data
        self._sensor_type = sensor_type
        self._device_id = device.device_id
        self._sensor_value = None

        sensor_type_name = sensor_type[0].value.replace("_", " ").title()
        self._name = '{} {} {}'.format(location.name,
                                       device.name,
                                       sensor_type_name)

    @property
    def name(self):
        """Return the name of the Canary sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensor_type[0] == SensorType.AIR_QUALITY:
            if self._sensor_value <= .4:
                return "Very Abnormal"
            elif self._sensor_value <= .59:
                return "Abnormal"
            elif self._sensor_value <= 1.0:
                return "Normal"

        return self._sensor_value

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return "sensor_canary_{}_{}".format(self._device_id,
                                            self._sensor_type[0].value)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._sensor_type[1]

    @property
    def icon(self):
        """Icon for the sensor."""
        return self._sensor_type[2]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._sensor_type[0] == SensorType.AIR_QUALITY:
            return {
                ATTR_AIR_QUALITY_READING: self._sensor_value
            }

        return None

    def update(self):
        """Get the latest state of the sensor."""
        self._data.update()

        value = self._data.get_reading(self._device_id, self._sensor_type[0])
        self._sensor_value = round(float(value), SENSOR_VALUE_PRECISION)
