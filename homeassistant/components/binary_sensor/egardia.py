"""
Interfaces with Egardia/Woonveilig alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.egardia/
"""
import asyncio
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.components.egardia import (
    EGARDIA_DEVICE, ATTR_DISCOVER_DEVICES)
_LOGGER = logging.getLogger(__name__)

EGARDIA_TYPE_TO_DEVICE_CLASS = {'IR Sensor': 'motion',
                                'Door Contact': 'opening',
                                'IR': 'motion'}


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Initialize the platform."""
    if (discovery_info is None or
            discovery_info[ATTR_DISCOVER_DEVICES] is None):
        return

    disc_info = discovery_info[ATTR_DISCOVER_DEVICES]
    # multiple devices here!
    async_add_devices(
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
        """The name of the device."""
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
        """The device class."""
        return self._device_class
