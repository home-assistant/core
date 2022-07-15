"""Support for HomeKit Controller locks."""
from __future__ import annotations

from typing import Any

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.lock import STATE_JAMMED, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    STATE_LOCKED,
    STATE_UNKNOWN,
    STATE_UNLOCKED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES, HomeKitEntity

CURRENT_STATE_MAP = {
    0: STATE_UNLOCKED,
    1: STATE_LOCKED,
    2: STATE_JAMMED,
    3: STATE_UNKNOWN,
}

TARGET_STATE_MAP = {STATE_UNLOCKED: 0, STATE_LOCKED: 1}

REVERSED_TARGET_STATE_MAP = {v: k for k, v in TARGET_STATE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit lock."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if service.type != ServicesTypes.LOCK_MECHANISM:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        async_add_entities([HomeKitLock(conn, info)], True)
        return True

    conn.add_listener(async_add_service)


class HomeKitLock(HomeKitEntity, LockEntity):
    """Representation of a HomeKit Controller Lock."""

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE,
            CharacteristicsTypes.LOCK_MECHANISM_TARGET_STATE,
            CharacteristicsTypes.BATTERY_LEVEL,
        ]

    @property
    def is_locked(self) -> bool | None:
        """Return true if device is locked."""
        value = self.service.value(CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE)
        if CURRENT_STATE_MAP[value] == STATE_UNKNOWN:
            return None
        return CURRENT_STATE_MAP[value] == STATE_LOCKED

    @property
    def is_locking(self) -> bool:
        """Return true if device is locking."""
        current_value = self.service.value(
            CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE
        )
        target_value = self.service.value(
            CharacteristicsTypes.LOCK_MECHANISM_TARGET_STATE
        )
        return (
            CURRENT_STATE_MAP[current_value] == STATE_UNLOCKED
            and REVERSED_TARGET_STATE_MAP.get(target_value) == STATE_LOCKED
        )

    @property
    def is_unlocking(self) -> bool:
        """Return true if device is unlocking."""
        current_value = self.service.value(
            CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE
        )
        target_value = self.service.value(
            CharacteristicsTypes.LOCK_MECHANISM_TARGET_STATE
        )
        return (
            CURRENT_STATE_MAP[current_value] == STATE_LOCKED
            and REVERSED_TARGET_STATE_MAP.get(target_value) == STATE_UNLOCKED
        )

    @property
    def is_jammed(self) -> bool:
        """Return true if device is jammed."""
        value = self.service.value(CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE)
        return CURRENT_STATE_MAP[value] == STATE_JAMMED

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self._set_lock_state(STATE_LOCKED)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self._set_lock_state(STATE_UNLOCKED)

    async def _set_lock_state(self, state: str) -> None:
        """Send state command."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.LOCK_MECHANISM_TARGET_STATE: TARGET_STATE_MAP[state]}
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        attributes = {}

        battery_level = self.service.value(CharacteristicsTypes.BATTERY_LEVEL)
        if battery_level:
            attributes[ATTR_BATTERY_LEVEL] = battery_level

        return attributes
