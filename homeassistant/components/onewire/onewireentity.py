"""Support for 1-Wire environment sensors."""
from homeassistant.helpers.entity import Entity


class OneWireEntity(Entity):
    """Implementation of an One wire Sensor."""

    def __init__(self, name, device_file, sensor_type, proxy, initial_value):
        """Initialize the sensor."""
        self._name = f"{name} {sensor_type.capitalize()}"
        self._device_file = device_file
        self._value_raw = initial_value
        self._proxy = proxy
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {"device_file": self._device_file, "raw_value": self._value_raw}

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._device_file

    def read_value(self):
        """Read the value from the path."""
        return self._proxy.read_value(self._device_file)

    def write_value(self, value):
        """Write the value to the path."""
        self._proxy.write_value(self._device_file, value)
