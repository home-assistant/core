"""Suppoort for Amcrest IP camera binary sensors."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASS_MOTION)
from homeassistant.const import CONF_NAME, CONF_BINARY_SENSORS
from . import DATA_AMCREST, BINARY_SENSORS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up a binary sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    device_name = discovery_info[CONF_NAME]
    binary_sensors = discovery_info[CONF_BINARY_SENSORS]
    amcrest = hass.data[DATA_AMCREST][device_name]

    amcrest_binary_sensors = []
    for sensor_type in binary_sensors:
        amcrest_binary_sensors.append(
            AmcrestBinarySensor(amcrest.name, amcrest.device, sensor_type))

    async_add_devices(amcrest_binary_sensors, True)


class AmcrestBinarySensor(BinarySensorDevice):
    """Binary sensor for Amcrest camera."""

    def __init__(self, name, camera, sensor_type):
        """Initialize entity."""
        self._name = '{} {}'.format(name, BINARY_SENSORS[sensor_type])
        self._camera = camera
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
            self._state = self._camera.is_motion_detected
        except AmcrestError as error:
            _LOGGER.error(
                'Could not update %s binary sensor due to error: %s',
                self.name, error)
