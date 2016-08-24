"""
Support for Insteon FanLinc.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.insteon/
"""

import logging

from homeassistant.components.fan import (FanEntity, SUPPORT_SET_SPEED,
                                          SPEED_OFF, SPEED_LOW, SPEED_MED,
                                          SPEED_HIGH)
from homeassistant.components.insteon_hub import (InsteonDevice, INSTEON,
                                                  filter_devices,
                                                  InsteonCommandable)
from homeassistant.const import STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

DEVICE_CATEGORIES = [
    {
        'DevCat': 1,
        'SubCat': [46]
    }
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Insteon Hub light platform."""
    devs = []
    for device in filter_devices(INSTEON.devices, DEVICE_CATEGORIES):
        devs.append(InsteonFanDevice(device))
    add_devices(devs)


class InsteonFanDevice(InsteonDevice, FanEntity):
    """Represet an insteon fan device."""

    def __init__(self: InsteonDevice, node: InsteonCommandable) -> None:
        """Initialize the device."""
        super(InsteonFanDevice, self).__init__(node)
        self.speed = STATE_UNKNOWN  # Insteon hub can't get state via REST

    def turn_on(self: InsteonDevice, speed: str=None):
        """Turn the fan on."""
        self.set_speed(speed if speed else SPEED_MED)

    def turn_off(self: InsteonDevice):
        """Turn the fan off."""
        self.set_speed(SPEED_OFF)

    def set_speed(self: InsteonDevice, speed: str) -> None:
        """Set the fan speed."""
        if self._send_command('fan', payload={'speed', speed}):
            self.speed = speed

    @property
    def supported_features(self: InsteonDevice) -> int:
        """Get the supported features for device."""
        return SUPPORT_SET_SPEED

    @property
    def speed_list(self: InsteonDevice) -> list:
        """Get the available speeds for the fan."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MED, SPEED_HIGH]

    @property
    def state(self: InsteonDevice) -> str:
        """Get the current device state."""
        return self.speed
