"""The AIS tracker base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AisTrackerCoordinator


class AistrackerEntity(CoordinatorEntity[AisTrackerCoordinator]):
    """Representation of a AIS tracker entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AisTrackerCoordinator,
        mmsi: str,
    ) -> None:
        """Initialize a AIS tracker entity."""
        super().__init__(coordinator)
        self._mmsi = mmsi
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mmsi)}, name=mmsi, serial_number=mmsi
        )

    @property
    def data(self) -> dict[str, float | int | str | None] | None:
        """Return the data."""
        return self.coordinator.data.get(self._mmsi)
