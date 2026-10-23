"""Locks on Zigbee Home Automation networks."""

import functools
from typing import Any, override

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation Door Lock from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.LOCK]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, ZhaDoorLock, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class ZhaDoorLock(ZHAEntity, LockEntity):
    """Representation of a ZHA lock."""

    _attr_translation_key: str = "door_lock"

    @property
    @override
    def is_locked(self) -> bool:
        """Return true if entity is locked."""
        return self._zha_state.is_locked

    @convert_zha_error_to_ha_error()
    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self.entity_data.entity.async_lock()
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self.entity_data.entity.async_unlock()
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    async def async_set_lock_user_code(self, code_slot: int, user_code: str) -> None:
        """Set the user_code to index X on the lock."""
        await self.entity_data.entity.async_set_lock_user_code(
            code_slot=code_slot, user_code=user_code
        )
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    async def async_enable_lock_user_code(self, code_slot: int) -> None:
        """Enable user_code at index X on the lock."""
        await self.entity_data.entity.async_enable_lock_user_code(code_slot=code_slot)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    async def async_disable_lock_user_code(self, code_slot: int) -> None:
        """Disable user_code at index X on the lock."""
        await self.entity_data.entity.async_disable_lock_user_code(code_slot=code_slot)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error()
    async def async_clear_lock_user_code(self, code_slot: int) -> None:
        """Clear the user_code at index X on the lock."""
        await self.entity_data.entity.async_clear_lock_user_code(code_slot=code_slot)
        self.async_write_ha_state()

    @callback
    @override
    def restore_external_state_attributes(self, state: State) -> None:
        """Restore entity state."""
        self.entity_data.entity.restore_external_state_attributes(
            state=state.state,
        )
