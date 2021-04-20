"""Support for locks through the SmartThings cloud API."""
from __future__ import annotations

from collections.abc import Sequence

from pysmartthings import Attribute, Capability

from homeassistant.components.lock import LockEntity

from . import SmartThingsEntity
from .const import DATA_BROKERS, DOMAIN

ST_STATE_LOCKED = "locked"
ST_LOCK_ATTR_MAP = {
    "codeId": "code_id",
    "codeName": "code_name",
    "lockName": "lock_name",
    "method": "method",
    "timeout": "timeout",
    "usedCode": "used_code",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add locks for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [
            SmartThingsLock(device)
            for device in broker.devices.values()
            if broker.any_assigned(device.device_id, "lock")
        ]
    )


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    if Capability.lock in capabilities:
        return [Capability.lock]
    return None


class SmartThingsLock(SmartThingsEntity, LockEntity):
    """Define a SmartThings lock."""

    async def async_lock(self, **kwargs):
        """Lock the device."""
        await self._device.lock(set_status=True)
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlock the device."""
        await self._device.unlock(set_status=True)
        self.async_write_ha_state()

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._device.status.lock == ST_STATE_LOCKED

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        state_attrs = {}
        status = self._device.status.attributes[Attribute.lock]
        if status.value:
            state_attrs["lock_state"] = status.value
        if isinstance(status.data, dict):
            for st_attr, ha_attr in ST_LOCK_ATTR_MAP.items():
                data_val = status.data.get(st_attr)
                if data_val is not None:
                    state_attrs[ha_attr] = data_val
        return state_attrs
