"""
Support for Vanderbilt (formerly Siemens) SPC alarm systems.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.spc/
"""
import logging
import asyncio

from homeassistant.components.spc import (
    ATTR_DISCOVER_DEVICES, DATA_REGISTRY)
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import (STATE_UNAVAILABLE, STATE_ON, STATE_OFF)


_LOGGER = logging.getLogger(__name__)

SPC_TYPE_TO_DEVICE_CLASS = {'0': 'motion',
                            '1': 'opening',
                            '3': 'smoke'}


SPC_INPUT_TO_SENSOR_STATE = {'0': STATE_OFF,
                             '1': STATE_ON}


def _get_device_class(spc_type):
    return SPC_TYPE_TO_DEVICE_CLASS.get(spc_type, None)


def _get_sensor_state(spc_input):
    return SPC_INPUT_TO_SENSOR_STATE.get(spc_input, STATE_UNAVAILABLE)


def _create_sensor(hass, zone):
    return SpcBinarySensor(zone_id=zone['id'],
                           name=zone['zone_name'],
                           state=_get_sensor_state(zone['input']),
                           device_class=_get_device_class(zone['type']),
                           spc_registry=hass.data[DATA_REGISTRY])


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices,
                         discovery_info=None):
    """Initialize the platform."""
    if (discovery_info is None or
            discovery_info[ATTR_DISCOVER_DEVICES] is None):
        return

    async_add_devices(
        _create_sensor(hass, zone)
        for zone in discovery_info[ATTR_DISCOVER_DEVICES]
        if _get_device_class(zone['type']))


class SpcBinarySensor(BinarySensorDevice):
    """Represents a sensor based on an SPC zone."""

    def __init__(self, zone_id, name, state, device_class, spc_registry):
        """Initialize the sensor device."""
        self._zone_id = zone_id
        self._name = name
        self._state = state
        self._device_class = device_class

        spc_registry.register_sensor_device(zone_id, self)

    @asyncio.coroutine
    def async_update_from_spc(self, state):
        """Update the state of the device."""
        self._state = state
        yield from self.async_update_ha_state()

    @property
    def name(self):
        """The name of the device."""
        return self._name

    @property
    def is_on(self):
        """Whether the device is switched on."""
        return self._state == STATE_ON

    @property
    def hidden(self) -> bool:
        """Whether the device is hidden by default."""
        # these type of sensors are probably mainly used for automations
        return True

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_class(self):
        """The device class."""
        return self._device_class
