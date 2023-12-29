"""Bases for Tedee entities."""

from pytedee_async.lock import TedeeLock

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
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
            manufacturer="tedee",
            model=lock.lock_type,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._lock = self.coordinator.data[self._lock.lock_id]
        super()._handle_coordinator_update()
