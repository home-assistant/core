"""
Support for SleepIQ sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sleepiq/
"""
from homeassistant.components import sleepiq
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['sleepiq']
ICON = 'mdi:hotel'


# pylint: disable=too-few-public-methods
class SleepIQSensor(Entity):
    """Implementation of a SleepIQ sensor."""

    def __init__(self, sleepiq_data, bed_id, side, sensor_type):
        """Initialize the sensor."""
        self.client_name = sleepiq.SLEEP_NUMBER
        self._bed_id = bed_id
        self._side = side
        self._name = sleepiq.SENSOR_TYPES[sensor_type]
        self.sleepiq_data = sleepiq_data
        self.type = sensor_type
        self._state = None

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {} {} {}'.format(self.client_name, self.bed.name,
                                    self.side.sleeper.first_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

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

        self.bed = self.sleepiq_data.beds[self._bed_id]
        self.side = getattr(self.bed, self._side)

        if self.type == sleepiq.SLEEP_NUMBER:
            self._state = self.side.sleep_number
        # TODO throw error for anything else


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the SleepIQ sensors."""
    if discovery_info is None:
        return

    data = sleepiq.DATA

    dev = list()
    for bed_id, bed in data.beds.items():
        for side in sleepiq.SIDES:
            dev.append(SleepIQSensor(data, bed_id, side, sleepiq.SLEEP_NUMBER))
    add_devices(dev)
