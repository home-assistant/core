"""Support for HomeKit Controller locks."""
import logging

from homeassistant.components.lock import LockDevice
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, STATE_LOCKED, STATE_UNLOCKED)

from . import KNOWN_DEVICES, HomeKitEntity

DEPENDENCIES = ['homekit_controller']

_LOGGER = logging.getLogger(__name__)

STATE_JAMMED = 'jammed'

CURRENT_STATE_MAP = {
    0: STATE_UNLOCKED,
    1: STATE_LOCKED,
    2: STATE_JAMMED,
    3: None,
}

TARGET_STATE_MAP = {
    STATE_UNLOCKED: 0,
    STATE_LOCKED: 1,
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit Lock support."""
    if discovery_info is None:
        return
    accessory = hass.data[KNOWN_DEVICES][discovery_info['serial']]
    add_entities([HomeKitLock(accessory, discovery_info)], True)


class HomeKitLock(HomeKitEntity, LockDevice):
    """Representation of a HomeKit Controller Lock."""

    def __init__(self, accessory, discovery_info):
        """Initialise the Lock."""
        super().__init__(accessory, discovery_info)
        self._state = None
        self._battery_level = None

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes
        return [
            CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE,
            CharacteristicsTypes.LOCK_MECHANISM_TARGET_STATE,
            CharacteristicsTypes.BATTERY_LEVEL,
        ]

    def _update_lock_mechanism_current_state(self, value):
        self._state = CURRENT_STATE_MAP[value]

    def _update_battery_level(self, value):
        self._battery_level = value

    @property
    def is_locked(self):
        """Return true if device is locked."""
        return self._state == STATE_LOCKED

    async def async_lock(self, **kwargs):
        """Lock the device."""
        await self._set_lock_state(STATE_LOCKED)

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        await self._set_lock_state(STATE_UNLOCKED)

    async def _set_lock_state(self, state):
        """Send state command."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['lock-mechanism.target-state'],
                            'value': TARGET_STATE_MAP[state]}]
        await self._accessory.put_characteristics(characteristics)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        if self._battery_level is None:
            return None

        return {
            ATTR_BATTERY_LEVEL: self._battery_level,
        }
