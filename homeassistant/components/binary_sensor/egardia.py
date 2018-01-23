"""
Interfaces with Egardia/Woonveilig alarm control panel.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.egardia/
"""
import logging
import asyncio

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import (STATE_ON, STATE_OFF)
_LOGGER = logging.getLogger(__name__)
ATTR_DISCOVER_DEVICES = 'egardia_sensor'
D_EGARDIASYS = 'egardiadevice'

# TODO: add mapping to 'smoke'
EGARDIA_TYPE_TO_DEVICE_CLASS = {'IR Sensor': 'motion',
                                'Door Contact': 'opening',
                                'IR': 'motion'}
# TODO: add state for triggered motion sensor
# NOT USED FOR NOW since we do not know state of motion sensor
EGARDIA_INPUT_TO_STATES = {'': STATE_OFF, 'Open': STATE_ON}


def _get_device_class(egardia_type):
    return EGARDIA_TYPE_TO_DEVICE_CLASS.get(egardia_type, None)


def _get_sensor_state(egardia_input):
    if len(egardia_input) > 0:
        return STATE_ON
    else:
        return STATE_OFF
#    return EGARDIA_INPUT_TO_STATES.get(egardia_input, STATE_UNAVAILABLE)


def _create_sensor(hass, sensor):
    return EgardiaBinarySensor(hass, senid=sensor["id"],
                               name=sensor['name'],
                               state=_get_sensor_state(sensor['cond']),
                               device_class=_get_device_class(sensor['type'])
                               )


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices,
                         discovery_info=None):
    """Initialize the platform."""
    if (discovery_info is None or
            discovery_info[ATTR_DISCOVER_DEVICES] is None):
        return

    di = discovery_info[ATTR_DISCOVER_DEVICES]

    # multiple devices here!
    async_add_devices(
        _create_sensor(hass, di[sensor])
        for sensor in di
        )


class EgardiaBinarySensor(BinarySensorDevice):
    """Represents a sensor based on an Egardia sensor (IR, Door Contact)."""

    def __init__(self, hass, senid, name, state, device_class):
        """Initialize the sensor device."""
        self._id = senid
        self._name = name
        self._state = state
        self._device_class = device_class
        self._hass = hass
        # spc_registry.register_sensor_device(zone_id, self)

    # @asyncio.coroutine
    # def async_update_from_egardia(self, state, extra):
    #    """Update the state of the device."""
    #    self._state = state
    #    yield from self.async_update_ha_state()

    def update(self):
        """Update the status."""
        egardia_input = self._hass.data[D_EGARDIASYS].getsensorstate(self._id)
        self._state = _get_sensor_state(egardia_input)

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
    def should_poll(self):
        """Polling required."""
        return True

    @property
    def device_class(self):
        """The device class."""
        return self._device_class
