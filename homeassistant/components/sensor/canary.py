"""
Support for Canary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.canary/
"""

from homeassistant.components.canary import DATA_CANARY
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['canary']

SENSOR_VALUE_PRECISION = 2
ATTR_AIR_QUALITY = "air_quality"

# Sensor types are defined like so:
# sensor type name, unit_of_measurement, icon
SENSOR_TYPES = [
    ["temperature", TEMP_CELSIUS, "mdi:thermometer"],
    ["humidity", "%", "mdi:water-percent"],
    ["air_quality", None, "mdi:weather-windy"],
]

STATE_AIR_QUALITY_NORMAL = "normal"
STATE_AIR_QUALITY_ABNORMAL = "abnormal"
STATE_AIR_QUALITY_VERY_ABNORMAL = "very_abnormal"


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

        sensor_type_name = sensor_type[0].replace("_", " ").title()
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
        return self._sensor_value

    @property
    def unique_id(self):
        """Return the unique ID of this sensor."""
        return "{}_{}".format(self._device_id, self._sensor_type[0])

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
        if self._sensor_type[0] == "air_quality" \
                and self._sensor_value is not None:
            air_quality = None
            if self._sensor_value <= .4:
                air_quality = STATE_AIR_QUALITY_VERY_ABNORMAL
            elif self._sensor_value <= .59:
                air_quality = STATE_AIR_QUALITY_ABNORMAL
            elif self._sensor_value <= 1.0:
                air_quality = STATE_AIR_QUALITY_NORMAL

            return {
                ATTR_AIR_QUALITY: air_quality
            }

        return None

    def update(self):
        """Get the latest state of the sensor."""
        self._data.update()

        from canary.api import SensorType
        canary_sensor_type = None
        if self._sensor_type[0] == "air_quality":
            canary_sensor_type = SensorType.AIR_QUALITY
        elif self._sensor_type[0] == "temperature":
            canary_sensor_type = SensorType.TEMPERATURE
        elif self._sensor_type[0] == "humidity":
            canary_sensor_type = SensorType.HUMIDITY

        value = self._data.get_reading(self._device_id, canary_sensor_type)

        if value is not None:
            self._sensor_value = round(float(value), SENSOR_VALUE_PRECISION)
