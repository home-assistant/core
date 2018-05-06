"""
This platform provides support for binary sensor data from RainMachine.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.rainmachine/
"""

from logging import getLogger

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.rainmachine import (
    DATA_RAINMACHINE, DATA_UPDATE_TOPIC, RainMachineEntity)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['rainmachine']

_LOGGER = getLogger(__name__)

ATTR_FREEZE = 'freeze'
ATTR_FREEZE_PROTECTION = 'freeze_protection'
ATTR_HOT_DAYS = 'extra_water_on_hot_days'
ATTR_HOURLY = 'hourly'
ATTR_MONTH = 'month'
ATTR_RAINDELAY = 'raindelay'
ATTR_RAINSENSOR = 'rainsensor'
ATTR_WEEKDAY = 'weekday'

SENSORS = {
    ATTR_FREEZE: ('Freeze Restrictions', 'mdi:cancel'),
    ATTR_FREEZE_PROTECTION: ('Freeze Protection', 'mdi:weather-snowy'),
    ATTR_HOT_DAYS: ('Extra Water on Hot Days', 'mdi:thermometer-lines'),
    ATTR_HOURLY: ('Hourly Restrictions', 'mdi:cancel'),
    ATTR_MONTH: ('Month Restrictions', 'mdi:cancel'),
    ATTR_RAINDELAY: ('Rain Delay Restrictions', 'mdi:cancel'),
    ATTR_RAINSENSOR: ('Rain Sensor Restrictions', 'mdi:cancel'),
    ATTR_WEEKDAY: ('Weekday Restrictions', 'mdi:cancel'),
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the RainMachine Switch platform."""
    if discovery_info is None:
        return

    _LOGGER.debug('Config received: %s', discovery_info)

    rainmachine = hass.data[DATA_RAINMACHINE]

    binary_sensors = []
    for sensor_type in discovery_info.get(
            CONF_MONITORED_CONDITIONS, SENSORS.keys()):
        try:
            name, icon = SENSORS[sensor_type]
            binary_sensors.append(
                RainMachineBinarySensor(rainmachine, sensor_type, name, icon))
        except KeyError:
            continue

    add_devices(binary_sensors, True)


class RainMachineBinarySensor(RainMachineEntity, BinarySensorDevice):
    """A sensor implementation for raincloud device."""

    def __init__(self, rainmachine, sensor_type, name, icon):
        """Initialize."""
        super().__init__(
            rainmachine, 'binary_sensor', sensor_type, name, icon=icon)

        self._sensor_type = sensor_type

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
        """Update the state."""
        if self._sensor_type == ATTR_FREEZE:
            self._state = self.rainmachine.restrictions['current']['freeze']
        elif self._sensor_type == ATTR_FREEZE_PROTECTION:
            self._state = self.rainmachine.restrictions['global'][
                'freezeProtectEnabled']
        elif self._sensor_type == ATTR_HOT_DAYS:
            self._state = self.rainmachine.restrictions['global'][
                'hotDaysExtraWatering']
        elif self._sensor_type == ATTR_HOURLY:
            self._state = self.rainmachine.restrictions['current']['hourly']
        elif self._sensor_type == ATTR_MONTH:
            self._state = self.rainmachine.restrictions['current']['month']
        elif self._sensor_type == ATTR_RAINDELAY:
            self._state = self.rainmachine.restrictions['current']['rainDelay']
        elif self._sensor_type == ATTR_RAINSENSOR:
            self._state = self.rainmachine.restrictions['current'][
                'rainSensor']
        elif self._sensor_type == ATTR_WEEKDAY:
            self._state = self.rainmachine.restrictions['current']['weekDay']
