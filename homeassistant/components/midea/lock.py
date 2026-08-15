"""Lock for Midea."""

from dataclasses import dataclass
from typing import Any, override

from midealocal.const import DeviceType

from homeassistant.components.lock import LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaLockEntityDescription(LockEntityDescription):
    """Description for a Midea lock entity."""

    models: list[DeviceType]


LOCKS: list[MideaLockEntityDescription] = [
    MideaLockEntityDescription(
        key="child_lock",
        translation_key="child_lock",
        models=[
            DeviceType.X34,
            DeviceType.A1,
            DeviceType.C2,
            DeviceType.CE,
            DeviceType.E1,
            DeviceType.ED,
            DeviceType.FA,
            DeviceType.FB,
            DeviceType.FC,
        ],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up locks for device."""
    device = config_entry.runtime_data

    async_add_entities(
        MideaLock(device, description)
        for description in LOCKS
        if device.device_type in description.models
        and device.attributes.get(description.key) is not None
    )


class MideaLock(MideaEntity, LockEntity):
    """Represent a Midea lock."""

    entity_description: MideaLockEntityDescription

    @property
    @override
    def is_locked(self) -> bool | None:
        """Return true if the child lock is engaged."""
        value = self._device.get_attribute(self.entity_description.key)
        if not isinstance(value, bool):
            return None
        return value

    @override
    def lock(self, **kwargs: Any) -> None:
        """Engage the child lock."""
        with midea_api_call():
            self._device.set_attribute(attr=self.entity_description.key, value=True)

    @override
    def unlock(self, **kwargs: Any) -> None:
        """Disengage the child lock."""
        with midea_api_call():
            self._device.set_attribute(attr=self.entity_description.key, value=False)
