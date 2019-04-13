"""Support for Sesame, by CANDY HOUSE."""
from typing import Callable
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.lock import LockDevice, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, CONF_EMAIL, CONF_PASSWORD,
    STATE_LOCKED, STATE_UNLOCKED)
from homeassistant.helpers.typing import ConfigType

ATTR_DEVICE_ID = 'device_id'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_platform(
        hass, config: ConfigType,
        add_entities: Callable[[list], None], discovery_info=None):
    """Set up the Sesame platform."""
    import pysesame

    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)

    add_entities([SesameDevice(sesame) for sesame in
                  pysesame.get_sesames(email, password)],
                 update_before_add=True)


class SesameDevice(LockDevice):
    """Representation of a Sesame device."""

    def __init__(self, sesame: object) -> None:
        """Initialize the Sesame device."""
        self._sesame = sesame

        # Cached properties from pysesame object.
        self._device_id = None
        self._nickname = None
        self._is_unlocked = False
        self._api_enabled = False
        self._battery = -1

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._nickname

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api_enabled

    @property
    def is_locked(self) -> bool:
        """Return True if the device is currently locked, else False."""
        return not self._is_unlocked

    @property
    def state(self) -> str:
        """Get the state of the device."""
        if self._is_unlocked:
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
        self._nickname = self._sesame.nickname
        self._api_enabled = self._sesame.api_enabled
        self._is_unlocked = self._sesame.is_unlocked
        self._device_id = self._sesame.device_id
        self._battery = self._sesame.battery

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        attributes = {}
        attributes[ATTR_DEVICE_ID] = self._device_id
        attributes[ATTR_BATTERY_LEVEL] = self._battery
        return attributes
