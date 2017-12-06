"""
Support for binary sensor using GC100.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.gc100/
"""
import voluptuous as vol

from homeassistant.components.gc100 import DATA_GC100, CONF_PORTS
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import DEVICE_DEFAULT_NAME
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['gc100']

_SENSORS_SCHEMA = vol.Schema({
    cv.string: cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORTS): vol.All(cv.ensure_list, [_SENSORS_SCHEMA])
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the GC100 devices."""
    binary_sensors = []
    ports = config.get(CONF_PORTS)
    for port in ports:
        for port_addr, port_name in port.items():
            binary_sensors.append(GC100BinarySensor(
                port_name, port_addr, hass.data[DATA_GC100]))
    add_devices(binary_sensors, True)


class GC100BinarySensor(BinarySensorDevice):
    """Representation of a binary sensor from GC100."""

    def __init__(self, name, port_addr, gc100):
        """Initialize the GC100 binary sensor."""
        # pylint: disable=no-member
        self._name = name or DEVICE_DEFAULT_NAME
        self._port_addr = port_addr
        self._gc100 = gc100
        self._state = None

        # Subscribe to be notified about state changes (PUSH)
        self._gc100.subscribe(self._port_addr, self.set_state)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return the state of the entity."""
        return self._state

    def update(self):
        """Update the sensor state."""
        self._gc100.read_sensor(self._port_addr, self.set_state)

    def set_state(self, state):
        """Set the current state."""
        self._state = state == 1
        self.schedule_update_ha_state()
