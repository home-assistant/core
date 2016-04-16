"""
Support for Vera switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging

import homeassistant.util.dt as dt_util
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (
    ATTR_ARMED, ATTR_BATTERY_LEVEL, ATTR_LAST_TRIP_TIME, ATTR_TRIPPED,
    STATE_OFF, STATE_ON)
from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Find and return Vera switches."""
    add_devices_callback(
        VeraSwitch(device, VERA_CONTROLLER) for
        device in VERA_DEVICES['switch'])


class VeraSwitch(VeraDevice, SwitchDevice):
    """Representation of a Vera Switch."""

    def __init__(self, vera_device, controller):
        """Initialize the Vera device."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
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

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.vera_device.switch_on()
        self._state = STATE_ON
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.vera_device.switch_off()
        self._state = STATE_OFF
        self.update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Called by the vera device callback to update state."""
        self._state = self.vera_device.is_switched_on()
