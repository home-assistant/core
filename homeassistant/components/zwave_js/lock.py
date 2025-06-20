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
    DoorLockCCConfigurationSetOptions,
    DoorLockMode,
    OperationType,
)
from zwave_js_server.exceptions import BaseZwaveJSServerError
from zwave_js_server.util.lock import clear_usercode, set_configuration, set_usercode

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockEntity, LockState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_AUTO_RELOCK_TIME,
    ATTR_BLOCK_TO_BLOCK,
    ATTR_HOLD_AND_RELEASE_TIME,
    ATTR_LOCK_TIMEOUT,
    ATTR_OPERATION_TYPE,
    ATTR_TWIST_ASSIST,
    DATA_CLIENT,
    DOMAIN,
    LOGGER,
    SERVICE_CLEAR_LOCK_USERCODE,
    SERVICE_SET_LOCK_CONFIGURATION,
    SERVICE_SET_LOCK_USERCODE,
)
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

PARALLEL_UPDATES = 0

STATE_TO_ZWAVE_MAP: dict[int, dict[str, int | bool]] = {
    CommandClass.DOOR_LOCK: {
        LockState.UNLOCKED: DoorLockMode.UNSECURED,
        LockState.LOCKED: DoorLockMode.SECURED,
    },
    CommandClass.LOCK: {
        LockState.UNLOCKED: False,
        LockState.LOCKED: True,
    },
}
UNIT16_SCHEMA = vol.All(vol.Coerce(int), vol.Range(min=0, max=65535))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z-Wave lock from config entry."""
    client: ZwaveClient = config_entry.runtime_data[DATA_CLIENT]

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

    platform.async_register_entity_service(
        SERVICE_SET_LOCK_CONFIGURATION,
        {
            vol.Required(ATTR_OPERATION_TYPE): vol.All(
                cv.string,
                vol.Upper,
                vol.In(["TIMED", "CONSTANT"]),
                lambda x: OperationType[x],
            ),
            vol.Optional(ATTR_LOCK_TIMEOUT): UNIT16_SCHEMA,
            vol.Optional(ATTR_AUTO_RELOCK_TIME): UNIT16_SCHEMA,
            vol.Optional(ATTR_HOLD_AND_RELEASE_TIME): UNIT16_SCHEMA,
            vol.Optional(ATTR_TWIST_ASSIST): vol.Coerce(bool),
            vol.Optional(ATTR_BLOCK_TO_BLOCK): vol.Coerce(bool),
        },
        "async_set_lock_configuration",
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

    async def _set_lock_state(self, target_state: LockState, **kwargs: Any) -> None:
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
        await self._set_lock_state(LockState.LOCKED)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._set_lock_state(LockState.UNLOCKED)

    async def async_set_lock_usercode(self, code_slot: int, usercode: str) -> None:
        """Set the usercode to index X on the lock."""
        try:
            await set_usercode(self.info.node, code_slot, usercode)
        except BaseZwaveJSServerError as err:
            raise HomeAssistantError(
                f"Unable to set lock usercode on lock {self.entity_id} code_slot "
                f"{code_slot}: {err}"
            ) from err
        LOGGER.debug("User code at slot %s on lock %s set", code_slot, self.entity_id)

    async def async_clear_lock_usercode(self, code_slot: int) -> None:
        """Clear the usercode at index X on the lock."""
        try:
            await clear_usercode(self.info.node, code_slot)
        except BaseZwaveJSServerError as err:
            raise HomeAssistantError(
                f"Unable to clear lock usercode on lock {self.entity_id} code_slot "
                f"{code_slot}: {err}"
            ) from err
        LOGGER.debug(
            "User code at slot %s on lock %s cleared", code_slot, self.entity_id
        )

    async def async_set_lock_configuration(
        self,
        operation_type: OperationType,
        lock_timeout: int | None = None,
        auto_relock_time: int | None = None,
        hold_and_release_time: int | None = None,
        twist_assist: bool | None = None,
        block_to_block: bool | None = None,
    ) -> None:
        """Set the lock configuration."""
        params: dict[str, Any] = {"operation_type": operation_type}
        params.update(
            {
                attr: val
                for attr, val in (
                    ("lock_timeout_configuration", lock_timeout),
                    ("auto_relock_time", auto_relock_time),
                    ("hold_and_release_time", hold_and_release_time),
                    ("twist_assist", twist_assist),
                    ("block_to_block", block_to_block),
                )
                if val is not None
            }
        )
        configuration = DoorLockCCConfigurationSetOptions(**params)
        result = await set_configuration(
            self.info.node.endpoints[self.info.primary_value.endpoint or 0],
            configuration,
        )
        if result is None:
            return
        msg = f"Result status is {result.status}"
        if result.remaining_duration is not None:
            msg += f" and remaining duration is {result.remaining_duration!s}"
        LOGGER.info("%s after setting lock configuration for %s", msg, self.entity_id)
