"""
Support for Canary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.canary/
"""
from homeassistant.components.canary import DATA_CANARY
from homeassistant.const import TEMP_FAHRENHEIT, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['canary']

SENSOR_VALUE_PRECISION = 1


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Canary sensors."""
    data = hass.data[DATA_CANARY]
    devices = []

    from canary.api import SensorType
    for location in data.locations:
        for device in location.devices:
            if device.is_online:
                for sensor_type in SensorType:
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
        self._is_celsius = location.is_celsius
        self._sensor_value = None

        sensor_type_name = sensor_type.value.replace("_", " ").title()
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
        return "sensor_canary_{}_{}".format(self._device_id,
                                            self._sensor_type.value)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        from canary.api import SensorType
        if self._sensor_type == SensorType.TEMPERATURE:
            return TEMP_CELSIUS if self._is_celsius else TEMP_FAHRENHEIT
        elif self._sensor_type == SensorType.HUMIDITY:
            return "%"
        elif self._sensor_type == SensorType.AIR_QUALITY:
            return ""
        return None

    def update(self):
        """Get the latest state of the sensor."""
        self._data.update()

        readings = self._data.get_readings(self._device_id)
        value = next((
            reading.value for reading in readings
            if reading.sensor_type == self._sensor_type), None)
        if value is not None:
            self._sensor_value = round(float(value), SENSOR_VALUE_PRECISION)
