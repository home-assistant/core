"""Demo platform that has a couple of fake locks."""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.lock import (
    LockEntity,
    LockEntityDescription,
    LockEntityFeature,
    LockState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


@dataclass(frozen=True, kw_only=True)
class DemoLockEntityDescription(LockEntityDescription):
    """Describes a demo lock."""

    state: LockState
    features: LockEntityFeature


LOCKS = (
    DemoLockEntityDescription(
        key="kitchen_sink_lock_001",
        name="Openable lock",
        state=LockState.LOCKED,
        features=LockEntityFeature.OPEN,
    ),
    DemoLockEntityDescription(
        key="kitchen_sink_lock_002",
        name="Another openable lock",
        state=LockState.UNLOCKED,
        features=LockEntityFeature.OPEN,
    ),
    DemoLockEntityDescription(
        key="kitchen_sink_lock_003",
        name="Basic lock",
        state=LockState.LOCKED,
        features=LockEntityFeature(0),
    ),
    DemoLockEntityDescription(
        key="kitchen_sink_lock_004",
        name="Another basic lock",
        state=LockState.UNLOCKED,
        features=LockEntityFeature(0),
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo locks."""
    async_add_entities(DemoLock(description) for description in LOCKS)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Everything but the Kitchen Sink config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoLock(LockEntity):
    """Representation of a Demo lock."""

    entity_description: DemoLockEntityDescription

    def __init__(self, description: DemoLockEntityDescription) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_unique_id = description.key
        self._attr_supported_features = description.features
        self._state = description.state
        self._attr_is_locking = False
        self._attr_is_unlocking = False

    @property
    @override
    def is_locked(self) -> bool:
        """Return true if lock is locked."""
        return self._state == LockState.LOCKED

    @property
    @override
    def is_open(self) -> bool:
        """Return true if lock is open."""
        return self._state == LockState.OPEN

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self._attr_is_locking = True
        self.async_write_ha_state()
        self._attr_is_locking = False
        self._state = LockState.LOCKED
        self.async_write_ha_state()

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self._attr_is_unlocking = True
        self.async_write_ha_state()
        self._attr_is_unlocking = False
        self._state = LockState.UNLOCKED
        self.async_write_ha_state()

    @override
    async def async_open(self, **kwargs: Any) -> None:
        """Open the door latch."""
        self._state = LockState.OPEN
        self.async_write_ha_state()
