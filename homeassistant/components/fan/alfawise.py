"""
Alfawise fan platform (fan is used as a humidifier).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/fan.alfawise/
"""
import logging
import ipaddress

import voluptuous as vol

from homeassistant.components.fan import (SPEED_LOW, SPEED_HIGH,
                                          FanEntity, SUPPORT_SET_SPEED)
from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_MAC
from homeassistant.const import STATE_OFF
from typing import Any
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyAlfawise==0.5-beta']


def isip(value: Any) -> str:
    """Validate that the value is an valid ip."""
    if value is None:
        raise vol.Invalid('an empty string is not a valid ip address')

    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise vol.Invalid('not a valid ip address')

    return value


DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_MAC): cv.string,
    vol.Required(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_DEVICES): {isip: DEVICE_SCHEMA}})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Alfawise fan platform."""
    import pyAlfawise
    fans = []
    for ipaddr, device_config in config[CONF_DEVICES].items():
        try:
            name = device_config[CONF_NAME]
            macaddr = device_config[CONF_MAC]
            _LOGGER.debug("Adding configured %s", name)
            device = pyAlfawise.Alfawise(macaddr, ipaddr)
            fan = AlfawiseFan(device, name)
            fans.append(fan)
        except pyAlfawise.AlfawiseError:
            raise PlatformNotReady

    add_devices(fans, True)


class AlfawiseFan(FanEntity):
    """An Alfawise fan entity."""

    def __init__(self, device, name):
        """Initialize the entity."""
        self._speed = STATE_OFF
        self._name = name
        self._fan = device

    def update(self):
        """Handle fan speed changes."""
        speed = self._fan.get_all_properties()[self._fan.OPTION_SPEED]
        if speed == self._fan.OFF:
            self._speed = STATE_OFF
        elif speed == self._fan.LOW:
            self._speed = SPEED_LOW
        elif speed == self._fan.HIGH:
            self._speed = SPEED_HIGH

    @property
    def name(self) -> str:
        """Get entity name."""
        return self._name

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._speed

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [STATE_OFF, SPEED_LOW, SPEED_HIGH]

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the entity."""
        if speed is None:
            speed = SPEED_LOW
        self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
        self.set_speed(STATE_OFF)

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed == SPEED_LOW:
            self._fan.turn_fan_on(self._fan.LOW)
        elif speed == SPEED_HIGH:
            self._fan.turn__fan_on(self._fan.HIGH)
        elif speed == STATE_OFF:
            self._fan.turn_fan_off()

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED
