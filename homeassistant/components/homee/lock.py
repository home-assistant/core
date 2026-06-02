"""The Homee lock platform."""

from typing import TYPE_CHECKING, Any

from pyHomee.const import AttributeChangedBy, AttributeType
from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity
from .helpers import get_name_for_enum, setup_homee_platform

PARALLEL_UPDATES = 0

LOCK_STATE_UNLOCKED = 0.0
LOCK_STATE_LOCKED = 1.0


def _determine_lock_state_open(attribute: HomeeAttribute) -> float | None:
    """Return the attribute value that momentarily unlatches the lock.

    Different homee-compatible locks encode the "open" (unlatch) command
    differently. The Hörmann SmartKey uses a signed range {-1, 0, 1}
    where -1 is unlatch; other devices extend above with {0, 1, 2}.
    Returns None when the device only supports two states.
    """
    if attribute.maximum == 2.0:
        return 2.0
    if attribute.minimum == -1.0:
        return -1.0
    return None


async def add_lock_entities(
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    nodes: list[HomeeNode],
) -> None:
    """Add homee lock entities."""
    async_add_entities(
        HomeeLock(attribute, config_entry)
        for node in nodes
        for attribute in node.attributes
        if (attribute.type == AttributeType.LOCK_STATE and attribute.editable)
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the homee platform for the lock component."""

    await setup_homee_platform(add_lock_entities, async_add_entities, config_entry)


class HomeeLock(HomeeEntity, LockEntity):
    """Representation of a Homee lock."""

    _attr_name = None

    def __init__(self, attribute: HomeeAttribute, entry: HomeeConfigEntry) -> None:
        """Initialize the homee lock."""
        super().__init__(attribute, entry)
        self._lock_state_open = _determine_lock_state_open(attribute)
        if self._lock_state_open is not None:
            self._attr_supported_features = LockEntityFeature.OPEN

    @property
    def is_locked(self) -> bool:
        """Return if lock is locked."""
        return self._attribute.current_value == LOCK_STATE_LOCKED

    @property
    def is_open(self) -> bool:
        """Return if lock is open (unlatched)."""
        # Require target_value too, so mid-transition away from "open" resolves
        # to is_locking/is_unlocking rather than OPEN (HA state precedence).
        return (
            self._lock_state_open is not None
            and self._attribute.current_value == self._lock_state_open
            and self._attribute.target_value == self._lock_state_open
        )

    @property
    def is_locking(self) -> bool:
        """Return if lock is locking."""
        return (
            self._attribute.target_value == LOCK_STATE_LOCKED
            and self._attribute.current_value != LOCK_STATE_LOCKED
        )

    @property
    def is_unlocking(self) -> bool:
        """Return if lock is unlocking."""
        return (
            self._attribute.target_value == LOCK_STATE_UNLOCKED
            and self._attribute.current_value != LOCK_STATE_UNLOCKED
        )

    @property
    def is_opening(self) -> bool:
        """Return if lock is opening (unlatching)."""
        return (
            self._lock_state_open is not None
            and self._attribute.target_value == self._lock_state_open
            and self._attribute.current_value != self._lock_state_open
        )

    @property
    def changed_by(self) -> str:
        """Return by whom or what the lock was last changed."""
        changed_id = str(self._attribute.changed_by_id)
        changed_by_name = get_name_for_enum(
            AttributeChangedBy, self._attribute.changed_by
        )
        if self._attribute.changed_by == AttributeChangedBy.USER:
            user = self._entry.runtime_data.get_user_by_id(
                self._attribute.changed_by_id
            )
            if user is not None:
                changed_id = user.username
            else:
                changed_id = "Unknown"

        return f"{changed_by_name}-{changed_id}"

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock specified lock. A code to lock the lock with may be specified."""
        await self.async_set_homee_value(LOCK_STATE_LOCKED)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock specified lock. A code to unlock the lock with may be specified."""
        await self.async_set_homee_value(LOCK_STATE_UNLOCKED)

    async def async_open(self, **kwargs: Any) -> None:
        """Open (unlatch) the lock."""
        if TYPE_CHECKING:
            assert self._lock_state_open is not None
        await self.async_set_homee_value(self._lock_state_open)
