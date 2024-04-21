"""Bases for Tedee entities."""

from pytedee_async.lock import TedeeLock

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TedeeApiCoordinator


class TedeeEntity(CoordinatorEntity[TedeeApiCoordinator]):
    """Base class for Tedee entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        lock: TedeeLock,
        coordinator: TedeeApiCoordinator,
        key: str,
    ) -> None:
        """Initialize Tedee entity."""
        super().__init__(coordinator)
        self._lock = lock
        self._attr_unique_id = f"{lock.lock_id}-{key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(lock.lock_id))},
            name=lock.lock_name,
            manufacturer="Tedee",
            model=lock.lock_type,
            via_device=(DOMAIN, coordinator.bridge.serial),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._lock = self.coordinator.data.get(self._lock.lock_id, self._lock)
        super()._handle_coordinator_update()


class TedeeDescriptionEntity(TedeeEntity):
    """Base class for Tedee device entities."""

    entity_description: EntityDescription

    def __init__(
        self,
        lock: TedeeLock,
        coordinator: TedeeApiCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize Tedee device entity."""
        super().__init__(lock, coordinator, entity_description.key)
        self.entity_description = entity_description
