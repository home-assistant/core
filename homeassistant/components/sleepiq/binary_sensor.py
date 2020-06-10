"""Support for SleepIQ sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity

from . import SleepIQSensor
from .const import DOMAIN, IS_IN_BED, SENSOR_TYPES, SIDES


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the SleepIQ sensors."""
    if discovery_info is None:
        return

    data = hass.data[DOMAIN]
    data.update()

    dev = []
    for bed_id, bed in data.beds.items():
        for side in SIDES:
            if getattr(bed, side) is not None:
                dev.append(IsInBedBinarySensor(data, bed_id, side))
    add_entities(dev)


class IsInBedBinarySensor(SleepIQSensor, BinarySensorEntity):
    """Implementation of a SleepIQ presence sensor."""

    def __init__(self, sleepiq_data, bed_id, side):
        """Initialize the sensor."""
        super().__init__(sleepiq_data, bed_id, side)
        self._state = None
        self._name = SENSOR_TYPES[IS_IN_BED]
        self.update()

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state is True

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return "occupancy"

    def update(self):
        """Get the latest data from SleepIQ and updates the states."""
        super().update()
        self._state = self.side.is_in_bed
