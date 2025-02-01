"""Support for HomeKit Controller locks."""

from __future__ import annotations

from typing import Any

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.lock import LockEntity, LockState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_BATTERY_LEVEL, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import HomeKitEntity

CURRENT_STATE_MAP = {
    0: LockState.UNLOCKED,
    1: LockState.LOCKED,
    2: LockState.JAMMED,
    3: STATE_UNKNOWN,
}

TARGET_STATE_MAP = {LockState.UNLOCKED: 0, LockState.LOCKED: 1}

REVERSED_TARGET_STATE_MAP = {v: k for k, v in TARGET_STATE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit lock."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        if service.type != ServicesTypes.LOCK_MECHANISM:
            return False
        info = {"aid": service.accessory.aid, "iid": service.iid}
        entity = HomeKitLock(conn, info)
        conn.async_migrate_unique_id(
            entity.old_unique_id, entity.unique_id, Platform.LOCK
        )
        async_add_entities([entity])
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
        return CURRENT_STATE_MAP[value] == LockState.LOCKED

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
            CURRENT_STATE_MAP[current_value] == LockState.UNLOCKED
            and REVERSED_TARGET_STATE_MAP.get(target_value) == LockState.LOCKED
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
            CURRENT_STATE_MAP[current_value] == LockState.LOCKED
            and REVERSED_TARGET_STATE_MAP.get(target_value) == LockState.UNLOCKED
        )

    @property
    def is_jammed(self) -> bool:
        """Return true if device is jammed."""
        value = self.service.value(CharacteristicsTypes.LOCK_MECHANISM_CURRENT_STATE)
        return CURRENT_STATE_MAP[value] == LockState.JAMMED

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self._set_lock_state(LockState.LOCKED)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self._set_lock_state(LockState.UNLOCKED)

    async def _set_lock_state(self, state: LockState) -> None:
        """Send state command."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.LOCK_MECHANISM_TARGET_STATE: TARGET_STATE_MAP[state]}
        )
        # Some locks need to be polled to update the current state
        # after a target state change.
        # https://github.com/home-assistant/core/issues/81887
        await self._accessory.async_request_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        attributes = {}

        battery_level = self.service.value(CharacteristicsTypes.BATTERY_LEVEL)
        if battery_level:
            attributes[ATTR_BATTERY_LEVEL] = battery_level

        return attributes
