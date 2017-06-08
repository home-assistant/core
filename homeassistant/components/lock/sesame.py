"""
Support for Sesame, by CANDY HOUSE.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/lock.sesame/
"""
from typing import Callable  # noqa
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.lock import LockDevice, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, CONF_EMAIL, CONF_PASSWORD,
    STATE_LOCKED, STATE_UNLOCKED)
from homeassistant.helpers.typing import ConfigType

REQUIREMENTS = ['pysesame==0.1.0']

ATTR_DEVICE_ID = 'device_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


# pylint: disable=unused-argument
def setup_platform(hass, config: ConfigType,
                   add_devices: Callable[[list], None], discovery_info=None):
    """Set up the Sesame platform."""
    import pysesame

    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)

    add_devices([SesameDevice(sesame) for
                 sesame in pysesame.get_sesames(email, password)])


class SesameDevice(LockDevice):
    """Representation of a Sesame device."""

    _sesame = None

    def __init__(self, sesame: object) -> None:
        """Initialize the Sesame device."""
        self._sesame = sesame

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._sesame.nickname

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._sesame.api_enabled

    @property
    def is_locked(self) -> bool:
        """Return True if the device is currently locked, else False."""
        return not self._sesame.is_unlocked

    @property
    def state(self) -> str:
        """Get the state of the device."""
        if self._sesame.is_unlocked:
            return STATE_UNLOCKED
        return STATE_LOCKED

    def lock(self, **kwargs) -> None:
        """Lock the device."""
        self._sesame.lock()

    def unlock(self, **kwargs) -> None:
        """Unlock the device."""
        self._sesame.unlock()

    def update(self) -> None:
        """Update the internal state of the device."""
        self._sesame.update_state()

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        attributes = {}
        attributes[ATTR_DEVICE_ID] = self._sesame.device_id
        attributes[ATTR_BATTERY_LEVEL] = self._sesame.battery
        return attributes
