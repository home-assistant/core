"""Support for ISY locks."""

from typing import Any, override

from pyisy.constants import ISY_VALUE_UNKNOWN

from homeassistant.components.lock import LockEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ISYNodeEntity, ISYProgramEntity
from .models import IsyConfigEntry

VALUE_TO_STATE = {0: False, 100: True}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IsyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ISY lock platform."""
    isy_data = entry.runtime_data
    devices = isy_data.devices
    entities: list[ISYLockEntity | ISYLockProgramEntity] = [
        ISYLockEntity(node, devices.get(node.primary_node))
        for node in isy_data.nodes[Platform.LOCK]
    ]

    entities.extend(
        ISYLockProgramEntity(name, status, actions)
        for name, status, actions in isy_data.programs[Platform.LOCK]
    )

    async_add_entities(entities)


class ISYLockEntity(ISYNodeEntity, LockEntity):
    """Representation of an ISY lock device."""

    @property
    @override
    def is_locked(self) -> bool | None:
        """Get whether the lock is in locked state."""
        if self._node.status == ISY_VALUE_UNKNOWN:
            return None
        return VALUE_TO_STATE.get(self._node.status)

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Send the lock command to the ISY device."""
        if not await self._node.secure_lock():
            raise HomeAssistantError(f"Unable to lock device {self._node.address}")

    @override
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
    @override
    def is_locked(self) -> bool:
        """Return true if the device is locked."""
        return bool(self._node.status)

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        if not await self._actions.run_then():
            raise HomeAssistantError(f"Unable to lock device {self._node.address}")

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        if not await self._actions.run_else():
            raise HomeAssistantError(f"Unable to unlock device {self._node.address}")
