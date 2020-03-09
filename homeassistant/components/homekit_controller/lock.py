"""Support for HomeKit Controller locks."""
import logging

from homekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.lock import LockDevice
from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)

STATE_JAMMED = "jammed"

CURRENT_STATE_MAP = {0: STATE_UNLOCKED, 1: STATE_LOCKED, 2: STATE_JAMMED, 3: None}

TARGET_STATE_MAP = {STATE_UNLOCKED: 0, STATE_LOCKED: 1}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit lock."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        if service["stype"] != "lock-mechanism":
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([HomeKitLock(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitLock(HomeKitEntity, LockDevice):
    """Representation of a HomeKit Controller Lock."""

    def __init__(self, accessory, discovery_info):
        """Initialise the Lock."""
        super().__init__(accessory, discovery_info)
        self._state = None
        self._battery_level = None

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
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
        characteristics = [
            {
                "aid": self._aid,
                "iid": self._chars["lock-mechanism.target-state"],
                "value": TARGET_STATE_MAP[state],
            }
        ]
        await self._accessory.put_characteristics(characteristics)

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        if self._battery_level is None:
            return None

        return {ATTR_BATTERY_LEVEL: self._battery_level}
