"""Support for HomeKit Controller locks."""
import logging

from aiohomekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.lock import LockEntity
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


class HomeKitLock(HomeKitEntity, LockEntity):
    """Representation of a HomeKit Controller Lock."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE,
            CharacteristicsTypes.LOCK_MECHANISM_TARGET_STATE,
            CharacteristicsTypes.BATTERY_LEVEL,
        ]

    @property
    def is_locked(self):
        """Return true if device is locked."""
        value = self.service.value(CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE)
        return CURRENT_STATE_MAP[value] == STATE_LOCKED

    async def async_lock(self, **kwargs):
        """Lock the device."""
        await self._set_lock_state(STATE_LOCKED)

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        await self._set_lock_state(STATE_UNLOCKED)

    async def _set_lock_state(self, state):
        """Send state command."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.LOCK_MECHANISM_TARGET_STATE: TARGET_STATE_MAP[state]}
        )

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        attributes = {}

        battery_level = self.service.value(CharacteristicsTypes.BATTERY_LEVEL)
        if battery_level:
            attributes[ATTR_BATTERY_LEVEL] = battery_level

        return attributes
