"""
Support for Wink fans.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.wink/
"""
import logging

from homeassistant.components.fan import (
    SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM, STATE_UNKNOWN, SUPPORT_DIRECTION,
    SUPPORT_SET_SPEED, FanEntity)
from homeassistant.components.wink import DOMAIN, WinkDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['wink']

SPEED_AUTO = 'auto'
SPEED_LOWEST = 'lowest'
SUPPORTED_FEATURES = SUPPORT_DIRECTION + SUPPORT_SET_SPEED


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink platform."""
    import pywink

    for fan in pywink.get_fans():
        if fan.object_id() + fan.name() not in hass.data[DOMAIN]['unique_ids']:
            add_entities([WinkFanDevice(fan, hass)])


class WinkFanDevice(WinkDevice, FanEntity):
    """Representation of a Wink fan."""

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['fan'].append(self)

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self.wink.set_fan_direction(direction)

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        self.wink.set_state(True, speed)

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the fan."""
        self.wink.set_state(True, speed)

    def turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        self.wink.set_state(False)

    @property
    def is_on(self):
        """Return true if the entity is on."""
        return self.wink.state()

    @property
    def speed(self) -> str:
        """Return the current speed."""
        current_wink_speed = self.wink.current_fan_speed()
        if SPEED_AUTO == current_wink_speed:
            return SPEED_AUTO
        if SPEED_LOWEST == current_wink_speed:
            return SPEED_LOWEST
        if SPEED_LOW == current_wink_speed:
            return SPEED_LOW
        if SPEED_MEDIUM == current_wink_speed:
            return SPEED_MEDIUM
        if SPEED_HIGH == current_wink_speed:
            return SPEED_HIGH
        return STATE_UNKNOWN

    @property
    def current_direction(self):
        """Return direction of the fan [forward, reverse]."""
        return self.wink.current_fan_direction()

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        wink_supported_speeds = self.wink.fan_speeds()
        supported_speeds = []
        if SPEED_AUTO in wink_supported_speeds:
            supported_speeds.append(SPEED_AUTO)
        if SPEED_LOWEST in wink_supported_speeds:
            supported_speeds.append(SPEED_LOWEST)
        if SPEED_LOW in wink_supported_speeds:
            supported_speeds.append(SPEED_LOW)
        if SPEED_MEDIUM in wink_supported_speeds:
            supported_speeds.append(SPEED_MEDIUM)
        if SPEED_HIGH in wink_supported_speeds:
            supported_speeds.append(SPEED_HIGH)
        return supported_speeds

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORTED_FEATURES
