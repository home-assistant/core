"""Support for ISY locks."""
from __future__ import annotations

from typing import Any

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from .const import DOMAIN
from .entity import ISYNodeEntity, ISYProgramEntity
from .models import IsyData
from .services import (
    SERVICE_DELETE_USER_CODE_SCHEMA,
    SERVICE_DELETE_ZWAVE_LOCK_USER_CODE,
    SERVICE_SET_USER_CODE_SCHEMA,
    SERVICE_SET_ZWAVE_LOCK_USER_CODE,
)

VALUE_TO_STATE = {0: False, 100: True}


@callback
def async_setup_lock_services(hass: HomeAssistant) -> None:
    """Create lock-specific services for the ISY Integration."""
    platform = async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_ZWAVE_LOCK_USER_CODE,
        SERVICE_SET_USER_CODE_SCHEMA,
        "async_set_zwave_lock_user_code",
    )
    platform.async_register_entity_service(
        SERVICE_DELETE_ZWAVE_LOCK_USER_CODE,
        SERVICE_DELETE_USER_CODE_SCHEMA,
        "async_delete_zwave_lock_user_code",
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ISY lock platform."""
    isy_data: IsyData = hass.data[DOMAIN][entry.entry_id]
    devices: dict[str, DeviceInfo] = isy_data.devices
    entities: list[ISYLockEntity | ISYLockProgramEntity] = []
    for node in isy_data.nodes[Platform.LOCK]:
        entities.append(ISYLockEntity(node, devices.get(node.primary_node)))

    for name, status, actions in isy_data.programs[Platform.LOCK]:
        entities.append(ISYLockProgramEntity(name, status, actions))

    async_add_entities(entities)
    async_setup_lock_services(hass)


class ISYLockEntity(ISYNodeEntity, LockEntity):
    """Representation of an ISY lock device."""

    @property
    def is_locked(self) -> bool | None:
        """Get whether the lock is in locked state."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return VALUE_TO_STATE.get(self._node.status)

    async def async_lock(self, **kwargs: Any) -> None:
        """Send the lock command to the ISY device."""
        if not await self._node.secure_lock():
            raise HomeAssistantError(f"Unable to lock device {self._node.address}")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Send the unlock command to the ISY device."""
        if not await self._node.secure_unlock():
            raise HomeAssistantError(f"Unable to unlock device {self._node.address}")

    async def async_set_zwave_lock_user_code(self, user_num: int, code: int) -> None:
        """Set a user lock code for a Z-Wave Lock."""
        if not await self._node.set_zwave_lock_code(user_num, code):
            raise HomeAssistantError(
                f"Could not set user code {user_num} for {self._node.address}"
            )

    async def async_delete_zwave_lock_user_code(self, user_num: int) -> None:
        """Delete a user lock code for a Z-Wave Lock."""
        if not await self._node.delete_zwave_lock_code(user_num):
            raise HomeAssistantError(
                f"Could not delete user code {user_num} for {self._node.address}"
            )


class ISYLockProgramEntity(ISYProgramEntity, LockEntity):
    """Representation of a ISY lock program."""

    @property
    def is_locked(self) -> bool:
        """Return true if the device is locked."""
        return bool(self._node.status)

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        if not await self._actions.run_then():
            raise HomeAssistantError(f"Unable to lock device {self._node.address}")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        if not await self._actions.run_else():
            raise HomeAssistantError(f"Unable to unlock device {self._node.address}")
