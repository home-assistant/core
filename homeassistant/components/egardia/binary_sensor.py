"""Interfaces with Egardia/Woonveilig alarm control panel."""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import STATE_OFF, STATE_ON

from . import ATTR_DISCOVER_DEVICES, EGARDIA_DEVICE

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['egardia']

EGARDIA_TYPE_TO_DEVICE_CLASS = {
    'IR Sensor': 'motion',
    'Door Contact': 'opening',
    'IR': 'motion',
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Initialize the platform."""
    if (discovery_info is None or
            discovery_info[ATTR_DISCOVER_DEVICES] is None):
        return

    disc_info = discovery_info[ATTR_DISCOVER_DEVICES]

    async_add_entities(
        (
            EgardiaBinarySensor(
                sensor_id=disc_info[sensor]['id'],
                name=disc_info[sensor]['name'],
                egardia_system=hass.data[EGARDIA_DEVICE],
                device_class=EGARDIA_TYPE_TO_DEVICE_CLASS.get(
                    disc_info[sensor]['type'], None)
            )
            for sensor in disc_info
        ), True)


class EgardiaBinarySensor(BinarySensorDevice):
    """Represents a sensor based on an Egardia sensor (IR, Door Contact)."""

    def __init__(self, sensor_id, name, egardia_system, device_class):
        """Initialize the sensor device."""
        self._id = sensor_id
        self._name = name
        self._state = None
        self._device_class = device_class
        self._egardia_system = egardia_system

    def update(self):
        """Update the status."""
        egardia_input = self._egardia_system.getsensorstate(self._id)
        self._state = STATE_ON if egardia_input else STATE_OFF

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Whether the device is switched on."""
        return self._state == STATE_ON

    @property
    def hidden(self):
        """Whether the device is hidden by default."""
        # these type of sensors are probably mainly used for automations
        return True

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class
