"""
Support for Velbus Binary Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/velbus/
"""
import asyncio
import logging


import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_DEVICES
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.binary_sensor import PLATFORM_SCHEMA
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv


REQUIREMENTS = ['python-velbus==2.0.11']
DEPENDENCIES = ['velbus']
DOMAIN = 'binary_sensor'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [
        {
            vol.Required('module'): cv.positive_int,
            vol.Required('channel'): cv.positive_int,
            vol.Required(CONF_NAME): cv.string,
            vol.Optional('is_pushbutton'): cv.boolean
        }
    ])
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Velbus binary sensors."""
    add_devices(VelbusBinarySensor(sensor) for sensor in config[CONF_DEVICES])
    return True


class VelbusBinarySensor(BinarySensorDevice):
    """Representation of a Velbus Binary Sensor."""

    def __init__(self, binary_sensor):
        """Initialize a Velbus light."""
        self._name = binary_sensor[CONF_NAME]
        self._module = binary_sensor['module']
        self._channel = binary_sensor['channel']
        self._is_pushbutton = 'is_pushbutton' in binary_sensor \
                              and binary_sensor['is_pushbutton']
        self._state = False

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add listener for Velbus messages on bus."""
        self.hass.data['VelbusController'].subscribe(self._on_message)

    @callback
    def _on_message(self, message):
        import velbus
        if isinstance(message, velbus.PushButtonStatusMessage):
            if message.address == self._module and \
               self._channel in message.get_channels():
                if self._is_pushbutton:
                    if self._channel in message.closed:
                        self._toggle()
                    else:
                        pass
                else:
                    self._toggle()

    def _toggle(self):
        if self._state is True:
            self._state = False
        else:
            self._state = True
        self.schedule_update_ha_state()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the display name of this sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the sensor is on."""
        return self._state
