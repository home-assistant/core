"""
Support for Velbus Binary Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/velbus/
"""
import asyncio
import logging

from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.velbus import (VELBUS_MESSAGE)

_LOGGER = logging.getLogger(__name__)

"""
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
"""

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up Velbus binary sensors."""
    controller = hass.data['VelbusController']
    async_add_entities(
        VelbusBinarySensor(hass, binary_sensor, controller)
        for binary_sensor in discovery_info)
    return True


class VelbusBinarySensor(BinarySensorDevice):
    """Representation of a Velbus Binary Sensor."""

    def __init__(self, hass, binary_sensor, controller):
        """Initialize a Velbus light."""
        self._name = binary_sensor[CONF_NAME]
        self._module = binary_sensor['module']
        self._channel = binary_sensor['channel']
        self._is_pushbutton = 'is_pushbutton' in binary_sensor \
                              and binary_sensor['is_pushbutton']
        self._state = False
        self._controller = controller
        self._hass = hass

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add listener for Velbus messages on bus."""
        async_dispatcher_connect(
            self._hass, VELBUS_MESSAGE, self._on_message
        )

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
        self._hass.async_add_job(self.async_update_ha_state())

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
