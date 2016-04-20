"""
Demo platform that has a couple of fake sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.const import ATTR_BATTERY_LEVEL, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Demo sensors."""
    add_devices([
        DemoSensor('Outside Temperature', 15.6, TEMP_CELSIUS, 12),
        DemoSensor('Outside Humidity', 54, '%', None),
    ])


class DemoSensor(Entity):
    """Representation of a Demo sensor."""

    def __init__(self, name, state, unit_of_measurement, battery):
        """Initialize the sensor."""
        self._name = name
        self._state = state
        self._unit_of_measurement = unit_of_measurement
        self._battery = battery

    @property
    def should_poll(self):
        """No polling needed for a demo sensor."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._battery:
            return {
                ATTR_BATTERY_LEVEL: self._battery,
            }
