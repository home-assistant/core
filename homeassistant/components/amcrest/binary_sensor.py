"""Suppoort for Amcrest IP camera binary sensors."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASS_MOTION)
from homeassistant.const import CONF_NAME, CONF_BINARY_SENSORS

from .const import BINARY_SENSOR_SCAN_INTERVAL_SECS, DATA_AMCREST

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=BINARY_SENSOR_SCAN_INTERVAL_SECS)

BINARY_SENSORS = {
    'motion_detected': 'Motion Detected'
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a binary sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST]['devices'][name]
    async_add_entities(
        [AmcrestBinarySensor(name, device, sensor_type)
         for sensor_type in discovery_info[CONF_BINARY_SENSORS]],
        True)


class AmcrestBinarySensor(BinarySensorDevice):
    """Binary sensor for Amcrest camera."""

    def __init__(self, name, device, sensor_type):
        """Initialize entity."""
        self._name = '{} {}'.format(name, BINARY_SENSORS[sensor_type])
        self._api = device.api
        self._sensor_type = sensor_type
        self._state = None

    @property
    def name(self):
        """Return entity name."""
        return self._name

    @property
    def is_on(self):
        """Return if entity is on."""
        return self._state

    @property
    def device_class(self):
        """Return device class."""
        return DEVICE_CLASS_MOTION

    def update(self):
        """Update entity."""
        from amcrest import AmcrestError

        _LOGGER.debug('Pulling data from %s binary sensor', self._name)

        try:
            self._state = self._api.is_motion_detected
        except AmcrestError as error:
            _LOGGER.error(
                'Could not update %s binary sensor due to error: %s',
                self.name, error)
