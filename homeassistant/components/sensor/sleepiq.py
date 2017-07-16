"""
Support for SleepIQ sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sleepiq/
"""
from homeassistant.components import sleepiq

DEPENDENCIES = ['sleepiq']
ICON = 'mdi:hotel'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the SleepIQ sensors."""
    if discovery_info is None:
        return

    data = sleepiq.DATA
    data.update()

    dev = list()
    for bed_id, _ in data.beds.items():
        for side in sleepiq.SIDES:
            dev.append(SleepNumberSensor(data, bed_id, side))
    add_devices(dev)


class SleepNumberSensor(sleepiq.SleepIQSensor):
    """Implementation of a SleepIQ sensor."""

    def __init__(self, sleepiq_data, bed_id, side):
        """Initialize the sensor."""
        sleepiq.SleepIQSensor.__init__(self, sleepiq_data, bed_id, side)

        self._state = None
        self.type = sleepiq.SLEEP_NUMBER
        self._name = sleepiq.SENSOR_TYPES[self.type]

        self.update()

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
        sleepiq.SleepIQSensor.update(self)
        self._state = self.side.sleep_number
