"""Tedee lock entities."""

from typing import Any

from aiotedee import TedeeClientException, TedeeLock, TedeeLockState

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import TedeeApiCoordinator, TedeeConfigEntry
from .entity import TedeeEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TedeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tedee lock entity."""
    coordinator = entry.runtime_data

    def _async_add_new_lock(locks: list[TedeeLock]) -> None:
        entities: list[TedeeLockEntity] = []
        for lock in locks:
            if lock.is_enabled_pullspring:
                entities.append(TedeeLockWithLatchEntity(lock, coordinator))
            else:
                entities.append(TedeeLockEntity(lock, coordinator))
        async_add_entities(entities)

    coordinator.new_lock_callbacks.append(_async_add_new_lock)

    _async_add_new_lock(list(coordinator.data.values()))


class TedeeLockEntity(TedeeEntity, LockEntity):
    """A tedee lock that doesn't have pullspring enabled."""

    _attr_name = None

    def __init__(
        self,
        lock: TedeeLock,
        coordinator: TedeeApiCoordinator,
    ) -> None:
        """Initialize the lock."""
        super().__init__(lock, coordinator, "lock")

    @property
    def is_locked(self) -> bool | None:
        """Return true if lock is locked."""
        if self._lock.state in (
            TedeeLockState.HALF_OPEN,
            TedeeLockState.UNKNOWN,
        ):
            return None
        return self._lock.state == TedeeLockState.LOCKED

    @property
    def is_unlocking(self) -> bool:
        """Return true if lock is unlocking."""
        return self._lock.state == TedeeLockState.UNLOCKING

    @property
    def is_open(self) -> bool:
        """Return true if lock is open."""
        return self._lock.state == TedeeLockState.PULLED

    @property
    def is_opening(self) -> bool:
        """Return true if lock is opening."""
        return self._lock.state == TedeeLockState.PULLING

    @property
    def is_locking(self) -> bool:
        """Return true if lock is locking."""
        return self._lock.state == TedeeLockState.LOCKING

    @property
    def is_jammed(self) -> bool:
        """Return true if lock is jammed."""
        return self._lock.is_state_jammed

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self._lock.is_connected
            and self._lock.state != TedeeLockState.UNCALIBRATED
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door."""
        try:
            self._lock.state = TedeeLockState.UNLOCKING
            self.async_write_ha_state()

            await self.coordinator.tedee_client.unlock(self._lock.lock_id)
            await self.coordinator.async_request_refresh()
        except (TedeeClientException, Exception) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unlock_failed",
                translation_placeholders={"lock_id": str(self._lock.lock_id)},
            ) from ex

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the door."""
        try:
            self._lock.state = TedeeLockState.LOCKING
            self.async_write_ha_state()

            await self.coordinator.tedee_client.lock(self._lock.lock_id)
            await self.coordinator.async_request_refresh()
        except (TedeeClientException, Exception) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="lock_failed",
                translation_placeholders={"lock_id": str(self._lock.lock_id)},
            ) from ex


class TedeeLockWithLatchEntity(TedeeLockEntity):
    """A tedee lock but has pullspring enabled, so it additional features."""

    @property
    def supported_features(self) -> LockEntityFeature:
        """Flag supported features."""
        return LockEntityFeature.OPEN

    async def async_open(self, **kwargs: Any) -> None:
        """Open the door with pullspring."""
        try:
            self._lock.state = TedeeLockState.UNLOCKING
            self.async_write_ha_state()

            await self.coordinator.tedee_client.open(self._lock.lock_id)
            await self.coordinator.async_request_refresh()
        except (TedeeClientException, Exception) as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="open_failed",
                translation_placeholders={"lock_id": str(self._lock.lock_id)},
            ) from ex
