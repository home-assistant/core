"""
Support for SleepIQ sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sleepiq/
"""
from homeassistant.components import sleepiq
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['sleepiq']
SENSOR_TYPES = {
    'sleep_number': 'SleepNumber',
}


# pylint: disable=too-few-public-methods
class SleepIQSensor(Entity):
    """Implementation of a SleepIQ sensor."""

    def __init__(self, sleepiq_data, bed_name, side, sensor_type):
        """Initialize the sensor."""
        self.client_name = 'SleepNumber'
        self._bed_name = bed_name
        self._side = side
        self._name = SENSOR_TYPES[sensor_type]
        self.sleepiq_data = sleepiq_data
        self.type = sensor_type
        self._state = None

        if self.type == 'sleep_number':
            self._icon = 'mdi:hotel'
        elif self.type == 'is_in_bed':
            self._icon = 'mdi:sleep'

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {} {} {}'.format(self.client_name, self._bed_name,
                                    self._sleeper, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return sleepiq.ICON

    def update(self):
        """Get the latest data from SleepIQ and updates the states."""
        # Call the API for new sleepiq data. Each sensor will re-trigger this
        # same exact call, but thats fine. We cache results for a short period
        # of time to prevent hitting API limits.
        self.sleepiq_data.update()

        if self._side == 'right':
            status = self.sleepiq_data.right
        else:
            status = self.sleepiq_data.left

        self._sleeper = status['sleeper']

        if self.type == 'sleep_number':
            self._state = status['sleep_number']
        elif self.type == 'is_in_bed':
            self._state = status['is_in_bed']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the SleepIQ sensors."""
    if discovery_info is None:
        return

    data = sleepiq.DATA

    dev = list()
    dev.append(SleepIQSensor(sleepiq_data, data.bed_name, 'left', 'sleep_number'))
    dev.append(SleepIQSensor(sleepiq_data, sleepiq_data.bed_name, 'right', 'sleep_number'))

    # TODO move to binary sensor
    dev.append(SleepIQSensor(sleepiq_data, data.bed_name, 'left', 'is_in_bed'))
    dev.append(SleepIQSensor(sleepiq_data, data.bed_name, 'right', 'is_in_bed'))

    add_devices(dev)
