"""
Support for Vera lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.vera/
"""
import logging

import homeassistant.util.dt as dt_util
from homeassistant.components.light import ATTR_BRIGHTNESS, Light
from homeassistant.const import (
    ATTR_ARMED, ATTR_BATTERY_LEVEL, ATTR_LAST_TRIP_TIME, ATTR_TRIPPED,
    STATE_OFF, STATE_ON)
from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup Vera lights."""
    add_devices_callback(
        VeraLight(device, VERA_CONTROLLER) for device in VERA_DEVICES['light'])


class VeraLight(VeraDevice, Light):
    """Representation of a Vera Light, including dimmable."""

    def __init__(self, vera_device, controller):
        """Initialize the light."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self.vera_device.is_dimmable:
            return self.vera_device.get_brightness()

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs and self.vera_device.is_dimmable:
            self.vera_device.set_brightness(kwargs[ATTR_BRIGHTNESS])
        else:
            self.vera_device.switch_on()

        self._state = STATE_ON
        self.update_ha_state(True)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self.vera_device.switch_off()
        self._state = STATE_OFF
        self.update_ha_state()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level + '%'

        if self.vera_device.is_armable:
            armed = self.vera_device.is_armed
            attr[ATTR_ARMED] = 'True' if armed else 'False'

        if self.vera_device.is_trippable:
            last_tripped = self.vera_device.last_trip
            if last_tripped is not None:
                utc_time = dt_util.utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.is_tripped
            attr[ATTR_TRIPPED] = 'True' if tripped else 'False'

        attr['Vera Device Id'] = self.vera_device.vera_device_id
        return attr

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Called by the vera device callback to update state."""
        self._state = self.vera_device.is_switched_on()
