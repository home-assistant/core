"""
Z-Wave platform that handles fans.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.zwave/
"""
import logging
import math

from homeassistant.components.fan import (
    DOMAIN, FanEntity, SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
    SUPPORT_SET_SPEED)
from homeassistant.components import zwave
from homeassistant.components.zwave import async_setup_platform  # noqa pylint: disable=unused-import

_LOGGER = logging.getLogger(__name__)

SPEED_LIST = [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

# Value will first be divided to an integer
VALUE_TO_SPEED = {
    0: SPEED_OFF,
    1: SPEED_LOW,
    2: SPEED_MEDIUM,
    3: SPEED_HIGH,
}

SPEED_TO_VALUE = {
    SPEED_OFF: 0,
    SPEED_LOW: 1,
    SPEED_MEDIUM: 50,
    SPEED_HIGH: 99,
}


def get_device(values, **kwargs):
    """Create Z-Wave entity device."""
    return ZwaveFan(values)


class ZwaveFan(zwave.ZWaveDeviceEntity, FanEntity):
    """Representation of a Z-Wave fan."""

    def __init__(self, values):
        """Initialize the Z-Wave fan device."""
        zwave.ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self.update_properties()

    def update_properties(self):
        """Handle data changes for node values."""
        value = math.ceil(self.values.primary.data * 3 / 100)
        self._state = VALUE_TO_SPEED[value]

    def set_speed(self, speed):
        """Set the speed of the fan."""
        self.node.set_dimmer(
            self.values.primary.value_id, SPEED_TO_VALUE[speed])

    def turn_on(self, speed=None, **kwargs):
        """Turn the device on."""
        if speed is None:
            # Value 255 tells device to return to previous value
            self.node.set_dimmer(self.values.primary.value_id, 255)
        else:
            self.set_speed(speed)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.node.set_dimmer(self.values.primary.value_id, 0)

    @property
    def speed(self):
        """Return the current speed."""
        return self._state

    @property
    def speed_list(self):
        """Get the list of available speeds."""
        return SPEED_LIST

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES
