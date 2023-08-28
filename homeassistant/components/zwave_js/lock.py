"""Representation of Z-Wave locks."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.lock import (
    ATTR_CODE_SLOT,
    ATTR_USERCODE,
    LOCK_CMD_CLASS_TO_LOCKED_STATE_MAP,
    LOCK_CMD_CLASS_TO_PROPERTY_MAP,
    DoorLockMode,
)
from zwave_js_server.exceptions import BaseZwaveJSServerError
from zwave_js_server.util.lock import clear_usercode, set_usercode

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_CLIENT,
    DOMAIN,
    LOGGER,
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_SET_LOCK_USERCODE,
)
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

PARALLEL_UPDATES = 0

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
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        entities.append(ZWaveLock(config_entry, driver, info))

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_{config_entry.entry_id}_add_{LOCK_DOMAIN}", async_add_lock
        )
    )

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_LOCK_USERCODE,
        {
            vol.Required(ATTR_CODE_SLOT): vol.Coerce(int),
            vol.Required(ATTR_USERCODE): cv.string,
        },
        "async_set_lock_usercode",
    )

    platform.async_register_entity_service(
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
        value = self.info.primary_value
        if value.value is None or (
            value.command_class == CommandClass.DOOR_LOCK
            and value.value == DoorLockMode.UNKNOWN
        ):
            # guard missing value
            return None
        return (
            LOCK_CMD_CLASS_TO_LOCKED_STATE_MAP[CommandClass(value.command_class)]
            == self.info.primary_value.value
        )

    async def _set_lock_state(self, target_state: str, **kwargs: Any) -> None:
        """Set the lock state."""
        target_value = self.get_zwave_value(
            LOCK_CMD_CLASS_TO_PROPERTY_MAP[
                CommandClass(self.info.primary_value.command_class)
            ]
        )
        if target_value is not None:
            await self._async_set_value(
                target_value,
                STATE_TO_ZWAVE_MAP[self.info.primary_value.command_class][target_state],
            )

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._set_lock_state(STATE_LOCKED)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._set_lock_state(STATE_UNLOCKED)

    async def async_set_lock_usercode(self, code_slot: int, usercode: str) -> None:
        """Set the usercode to index X on the lock."""
        try:
            await set_usercode(self.info.node, code_slot, usercode)
        except BaseZwaveJSServerError as err:
            raise HomeAssistantError(
                f"Unable to set lock usercode on code_slot {code_slot}: {err}"
            ) from err
        LOGGER.debug("User code at slot %s set", code_slot)

    async def async_clear_lock_usercode(self, code_slot: int) -> None:
        """Clear the usercode at index X on the lock."""
        try:
            await clear_usercode(self.info.node, code_slot)
        except BaseZwaveJSServerError as err:
            raise HomeAssistantError(
                f"Unable to clear lock usercode on code_slot {code_slot}: {err}"
            ) from err
        LOGGER.debug("User code at slot %s cleared", code_slot)
