"""The Homee lock platform."""

from typing import Any

from pyHomee.const import AttributeChangedBy, AttributeType

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity
from .helpers import get_name_for_enum

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the Homee platform for the lock component."""

    async_add_devices(
        HomeeLock(attribute, config_entry)
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if (attribute.type == AttributeType.LOCK_STATE and attribute.editable)
    )


class HomeeLock(HomeeEntity, LockEntity):
    """Representation of a Homee lock."""

    _attr_name = None

    @property
    def is_locked(self) -> bool:
        """Return if lock is locked."""
        return self._attribute.current_value == 1.0

    @property
    def is_locking(self) -> bool:
        """Return if lock is locking."""
        return self._attribute.target_value > self._attribute.current_value

    @property
    def is_unlocking(self) -> bool:
        """Return if lock is unlocking."""
        return self._attribute.target_value < self._attribute.current_value

    @property
    def changed_by(self) -> str:
        """Return by whom or what the lock was last changed."""
        changed_id = str(self._attribute.changed_by_id)
        changed_by_name = get_name_for_enum(
            AttributeChangedBy, self._attribute.changed_by
        )
        if self._attribute.changed_by == AttributeChangedBy.USER:
            changed_id = self._entry.runtime_data.get_user_by_id(
                self._attribute.changed_by_id
            ).username

        return f"{changed_by_name}-{changed_id}"

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock specified lock. A code to lock the lock with may be specified."""
        await self.async_set_homee_value(1)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock specified lock. A code to unlock the lock with may be specified."""
        await self.async_set_homee_value(0)
