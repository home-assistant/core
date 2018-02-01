"""
Support for Insteon fans via local hub control.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/fan.insteon_local/
"""
import logging
from datetime import timedelta

from homeassistant.components.fan import (
    ATTR_SPEED, SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
    SUPPORT_SET_SPEED, FanEntity)
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.util as util

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon_local']
DOMAIN = 'fan'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

SUPPORT_INSTEON_LOCAL = SUPPORT_SET_SPEED


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Insteon local fan platform."""
    insteonhub = hass.data['insteon_local']
    if discovery_info is None:
        return

    linked = discovery_info['linked']
    device_list = []
    for device_id in linked:
        if (linked[device_id]['cat_type'] == 'dimmer' and
                linked[device_id]['sku'] == '2475F'):
            device = insteonhub.fan(device_id)
            device_list.append(
                InsteonLocalFanDevice(device)
            )

    add_devices(device_list)


class InsteonLocalFanDevice(FanEntity):
    """An abstract Class for an Insteon node."""

    def __init__(self, node):
        """Initialize the device."""
        self.node = node
        self._speed = SPEED_OFF

    @property
    def name(self):
        """Return the name of the node."""
        return self.node.device_id

    @property
    def unique_id(self):
        """Return the ID of this Insteon node."""
        return 'insteon_local_{}_fan'.format(self.node.device_id)

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._speed

    @property
    def speed_list(self: ToggleEntity) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update state of the fan."""
        resp = self.node.status()
        if 'cmd2' in resp:
            if resp['cmd2'] == '00':
                self._speed = SPEED_OFF
            elif resp['cmd2'] == '55':
                self._speed = SPEED_LOW
            elif resp['cmd2'] == 'AA':
                self._speed = SPEED_MEDIUM
            elif resp['cmd2'] == 'FF':
                self._speed = SPEED_HIGH

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_INSTEON_LOCAL

    def turn_on(self: ToggleEntity, speed: str=None, **kwargs) -> None:
        """Turn device on."""
        if speed is None:
            if ATTR_SPEED in kwargs:
                speed = kwargs[ATTR_SPEED]
            else:
                speed = SPEED_MEDIUM

        self.set_speed(speed)

    def turn_off(self: ToggleEntity, **kwargs) -> None:
        """Turn device off."""
        self.node.off()

    def set_speed(self: ToggleEntity, speed: str) -> None:
        """Set the speed of the fan."""
        if self.node.on(speed):
            self._speed = speed
