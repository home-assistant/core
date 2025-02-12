"""Support for locks through the SmartThings cloud API."""

from __future__ import annotations

from typing import Any

from pysmartthings.models import Attribute, Capability, Command

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SmartThingsConfigEntry
from .entity import SmartThingsEntity

ST_STATE_LOCKED = "locked"
ST_LOCK_ATTR_MAP = {
    "codeId": "code_id",
    "codeName": "code_name",
    "lockName": "lock_name",
    "method": "method",
    "timeout": "timeout",
    "usedCode": "used_code",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add lights for a config entry."""
    devices = entry.runtime_data.devices
    async_add_entities(
        SmartThingsLock(device) for device in devices if Capability.LOCK in device.data
    )


class SmartThingsLock(SmartThingsEntity, LockEntity):
    """Define a SmartThings lock."""

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.LOCK,
            Command.LOCK,
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        await self.coordinator.client.execute_device_command(
            self.coordinator.device.device_id,
            Capability.LOCK,
            Command.UNLOCK,
        )

    @property
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return (
            self.get_attribute_value(Capability.LOCK, Attribute.LOCK) == ST_STATE_LOCKED
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device specific state attributes."""
        state_attrs = {}
        status = self.coordinator.data[Capability.LOCK][Attribute.LOCK]
        if status.value:
            state_attrs["lock_state"] = status.value
        if isinstance(status.data, dict):
            for st_attr, ha_attr in ST_LOCK_ATTR_MAP.items():
                if (data_val := status.data.get(st_attr)) is not None:
                    state_attrs[ha_attr] = data_val
        return state_attrs
