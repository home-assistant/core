"""Support for Sesame, by CANDY HOUSE."""
from typing import Callable

import pysesame2
import voluptuous as vol

from homeassistant.components.lock import PLATFORM_SCHEMA, LockEntity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    CONF_API_KEY,
    STATE_LOCKED,
    STATE_UNLOCKED,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

ATTR_DEVICE_ID = "device_id"
ATTR_SERIAL_NO = "serial"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string})


def setup_platform(
    hass, config: ConfigType, add_entities: Callable[[list], None], discovery_info=None
):
    """Set up the Sesame platform."""
    api_key = config.get(CONF_API_KEY)

    add_entities(
        [SesameDevice(sesame) for sesame in pysesame2.get_sesames(api_key)],
        update_before_add=True,
    )


class SesameDevice(LockEntity):
    """Representation of a Sesame device."""

    def __init__(self, sesame: object) -> None:
        """Initialize the Sesame device."""
        self._sesame = sesame

        # Cached properties from pysesame object.
        self._device_id = None
        self._serial = None
        self._nickname = None
        self._is_locked = False
        self._responsive = False
        self._battery = -1

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._nickname

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._responsive

    @property
    def is_locked(self) -> bool:
        """Return True if the device is currently locked, else False."""
        return self._is_locked

    @property
    def state(self) -> str:
        """Get the state of the device."""
        return STATE_LOCKED if self._is_locked else STATE_UNLOCKED

    def lock(self, **kwargs) -> None:
        """Lock the device."""
        self._sesame.lock()

    def unlock(self, **kwargs) -> None:
        """Unlock the device."""
        self._sesame.unlock()

    def update(self) -> None:
        """Update the internal state of the device."""
        status = self._sesame.get_status()
        self._nickname = self._sesame.nickname
        self._device_id = str(self._sesame.id)
        self._serial = self._sesame.serial
        self._battery = status["battery"]
        self._is_locked = status["locked"]
        self._responsive = status["responsive"]

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes."""
        return {
            ATTR_DEVICE_ID: self._device_id,
            ATTR_SERIAL_NO: self._serial,
            ATTR_BATTERY_LEVEL: self._battery,
        }
