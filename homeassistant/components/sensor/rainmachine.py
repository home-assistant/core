"""
This platform provides support for sensor data from RainMachine.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.rainmachine/
"""

from logging import getLogger

from homeassistant.components.rainmachine import (
    DATA_RAINMACHINE,
    DATA_UPDATE_TOPIC,
    RainMachineEntity)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['rainmachine']

_LOGGER = getLogger(__name__)

ATTR_FREEZE_TEMP = 'freeze_protect_temp'

SENSORS = {
    ATTR_FREEZE_TEMP: ('Freeze Protect Temperature', 'mdi:thermometer', '°C'),
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the RainMachine Switch platform."""
    if discovery_info is None:
        return

    _LOGGER.debug('Config received: %s', discovery_info)

    rainmachine = hass.data[DATA_RAINMACHINE]

    sensors = []
    for sensor_type, attrs in discovery_info.get(
            CONF_MONITORED_CONDITIONS, SENSORS).items():
        name, icon, unit = attrs
        sensors.append(
            RainMachineSensor(rainmachine, sensor_type, name, icon, unit))

    add_devices(sensors, True)


class RainMachineSensor(RainMachineEntity):
    """A sensor implementation for raincloud device."""

    def __init__(self, rainmachine, sensor_type, name, icon, unit):
        """Initialize."""
        super().__init__(
            rainmachine, 'binary_sensor', sensor_type, name, icon=icon)

        self._sensor_type = sensor_type
        self._unit = unit

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    async def async_added_to_hass(self):
        """Register callbacks."""
        def update_data():
            """Update the state."""
            self.schedule_update_ha_state(True)

        async_dispatcher_connect(self.hass, DATA_UPDATE_TOPIC, update_data)

    def update(self):
        """Update the sensor's state."""
        if self._sensor_type == ATTR_FREEZE_TEMP:
            self._state = self.rainmachine.restrictions['global'][
                'freezeProtectTemp']
