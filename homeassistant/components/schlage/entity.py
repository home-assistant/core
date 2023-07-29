"""Base entity class for Schlage."""

from pyschlage.lock import Lock

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import LockData, SchlageDataUpdateCoordinator


class SchlageEntity(CoordinatorEntity[SchlageDataUpdateCoordinator]):
    """Base Schlage entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SchlageDataUpdateCoordinator, device_id: str
    ) -> None:
        """Initialize a Schlage entity."""
        super().__init__(coordinator=coordinator)
        self.device_id = device_id
        self._attr_unique_id = device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=self._lock.name,
            manufacturer=MANUFACTURER,
            model=self._lock.model_name,
            sw_version=self._lock.firmware_version,
        )

    @property
    def _lock_data(self) -> LockData:
        """Fetch the LockData from our coordinator."""
        return self.coordinator.data.locks[self.device_id]

    @property
    def _lock(self) -> Lock:
        """Fetch the Schlage lock from our coordinator."""
        return self._lock_data.lock

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # When is_locked is None the lock is unavailable.
        return super().available and self._lock.is_locked is not None
