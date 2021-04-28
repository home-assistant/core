"""Representation of Z-Wave locks."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import (
    ATTR_CODE_SLOT,
    ATTR_USERCODE,
    LOCK_CMD_CLASS_TO_LOCKED_STATE_MAP,
    LOCK_CMD_CLASS_TO_PROPERTY_MAP,
    CommandClass,
    DoorLockMode,
)
from zwave_js_server.model.value import Value as ZwaveValue
from zwave_js_server.util.lock import clear_usercode, set_usercode

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import AddEntitiesCallback

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)

STATE_TO_ZWAVE_MAP: dict[int, dict[str, int | bool]] = {
    CommandClass.DOOR_LOCK: {
        STATE_UNLOCKED: DoorLockMode.UNSECURED,
        STATE_LOCKED: DoorLockMode.SECURED,
    },
    CommandClass.LOCK: {
        STATE_UNLOCKED: False,
        STATE_LOCKED: True,
    },
}

SERVICE_SET_LOCK_USERCODE = "set_lock_usercode"
SERVICE_CLEAR_LOCK_USERCODE = "clear_lock_usercode"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave lock from config entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_lock(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Lock."""
        entities: list[ZWaveBaseEntity] = []
        entities.append(ZWaveLock(config_entry, client, info))

        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_{config_entry.entry_id}_add_{LOCK_DOMAIN}", async_add_lock
        )
    )

    platform = entity_platform.current_platform.get()
    assert platform

    platform.async_register_entity_service(  # type: ignore
        SERVICE_SET_LOCK_USERCODE,
        {
            vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
            vol.Required(ATTR_USERCODE): cv.string,
        },
        "async_set_lock_usercode",
    )

    platform.async_register_entity_service(  # type: ignore
        SERVICE_CLEAR_LOCK_USERCODE,
        {
            vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
        },
        "async_clear_lock_usercode",
    )


class ZWaveLock(ZWaveBaseEntity, LockEntity):
    """Representation of a Z-Wave lock."""

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return int(
            LOCK_CMD_CLASS_TO_LOCKED_STATE_MAP[
                CommandClass(self.info.primary_value.command_class)
            ]
        ) == int(self.info.primary_value.value)

    async def _set_lock_state(
        self, target_state: str, **kwargs: dict[str, Any]
    ) -> None:
        """Set the lock state."""
        target_value: ZwaveValue = self.get_zwave_value(
            LOCK_CMD_CLASS_TO_PROPERTY_MAP[self.info.primary_value.command_class]
        )
        if target_value is not None:
            await self.info.node.async_set_value(
                target_value,
                STATE_TO_ZWAVE_MAP[self.info.primary_value.command_class][target_state],
            )

    async def async_lock(self, **kwargs: dict[str, Any]) -> None:
        """Lock the lock."""
        await self._set_lock_state(STATE_LOCKED)

    async def async_unlock(self, **kwargs: dict[str, Any]) -> None:
        """Unlock the lock."""
        await self._set_lock_state(STATE_UNLOCKED)

    async def async_set_lock_usercode(self, code_slot: int, usercode: str) -> None:
        """Set the usercode to index X on the lock."""
        await set_usercode(self.info.node, code_slot, usercode)
        LOGGER.debug("User code at slot %s set", code_slot)

    async def async_clear_lock_usercode(self, code_slot: int) -> None:
        """Clear the usercode at index X on the lock."""
        await clear_usercode(self.info.node, code_slot)
        LOGGER.debug("User code at slot %s cleared", code_slot)
