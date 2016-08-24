"""
Support for SleepIQ sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sleepiq/
"""
from homeassistant.components import sleepiq
from homeassistant.components.binary_sensor import BinarySensorDevice

DEPENDENCIES = ['sleepiq']
ICON = 'mdi:sleep'

SENSOR_TYPES = {
    'is_in_bed': 'Is In Bed',
}


class SleepIQBinarySensor(BinarySensorDevice):
    """Implementation of a SleepIQ presence sensor."""

    def __init__(self, sleepiq_data, bed_name, side, sensor_type):
        """Initialize the sensor."""
        self.client_name = 'SleepNumber'
        self._bed_name = bed_name
        self._side = side
        self._name = SENSOR_TYPES[sensor_type]
        self.sleepiq_data = sleepiq_data
        self.type = sensor_type
        self._state = None
        self._sensor_class = 'motion'

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {} {} {}'.format(self.client_name, self._bed_name,
                                    self._sleeper, self._name)
    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state == True

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data from SleepIQ and updates the states."""
        # Call the API for new sleepiq data. Each sensor will re-trigger this
        # same exact call, but thats fine. We cache results for a short period
        # of time to prevent hitting API limits.
        self.sleepiq_data.update()

        status = self.sleepiq_data.sides[self._side]
        self._sleeper = status['sleeper']

        if self.type == 'is_in_bed':
            self._state = status['is_in_bed']
        # TODO throw error for anything else


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the SleepIQ sensors."""
    if discovery_info is None:
        return

    data = sleepiq.DATA

    dev = list()
    dev.append(SleepIQBinarySensor(data, data.bed_name, 'left', 'is_in_bed'))
    dev.append(SleepIQBinarySensor(data, data.bed_name, 'right', 'is_in_bed'))
    add_devices(dev)
