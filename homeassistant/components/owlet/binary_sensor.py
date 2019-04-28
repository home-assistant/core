"""Support for Owlet binary sensors."""
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.util import dt as dt_util

from . import DOMAIN as OWLET_DOMAIN
from .const import SENSOR_BASE_STATION, SENSOR_MOVEMENT

SCAN_INTERVAL = timedelta(seconds=120)

BINARY_CONDITIONS = {
    SENSOR_BASE_STATION: {
        'name': 'Base Station',
        'device_class': 'power'
    },
    SENSOR_MOVEMENT: {
        'name': 'Movement',
        'device_class': 'motion'
    }
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up owlet binary sensor."""
    if discovery_info is None:
        return

    device = hass.data[OWLET_DOMAIN]

    entities = []
    for condition in BINARY_CONDITIONS:
        if condition in device.monitor:
            entities.append(OwletBinarySensor(device, condition))

    add_entities(entities, True)


class OwletBinarySensor(BinarySensorDevice):
    """Representation of owlet binary sensor."""

    def __init__(self, device, condition):
        """Init owlet binary sensor."""
        self._device = device
        self._condition = condition
        self._state = None
        self._base_on = False
        self._prop_expiration = None
        self._is_charging = None

    @property
    def name(self):
        """Return sensor name."""
        return '{} {}'.format(self._device.name,
                              BINARY_CONDITIONS[self._condition]['name'])

    @property
    def is_on(self):
        """Return current state of sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the device class."""
        return BINARY_CONDITIONS[self._condition]['device_class']

    def update(self):
        """Update state of sensor."""
        self._base_on = self._device.device.base_station_on
        self._prop_expiration = self._device.device.prop_expire_time
        self._is_charging = self._device.device.charge_status > 0

        # handle expired values
        if self._prop_expiration < dt_util.now().timestamp():
            self._state = False
            return

        if self._condition == 'movement':
            if not self._base_on or self._is_charging:
                return False

        self._state = getattr(self._device.device, self._condition)
