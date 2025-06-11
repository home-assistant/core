"""Base entity for Tilt Pi integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TiltPiDataUpdateCoordinator
from .model import TiltHydrometerData


class TiltEntity(CoordinatorEntity[TiltPiDataUpdateCoordinator]):
    """Base class for Tilt entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TiltPiDataUpdateCoordinator,
        hydrometer: TiltHydrometerData,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._mac_id = hydrometer.mac_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hydrometer.mac_id)},
            name=f"Tilt {hydrometer.color}",
            manufacturer="Tilt Hydrometer",
            model=f"{hydrometer.color} Tilt Hydrometer",
        )

    @property
    def current_hydrometer(self) -> TiltHydrometerData:
        """Return the current hydrometer data for this entity."""
        return self.coordinator.data[self._mac_id]

    @property
    def available(self) -> bool:
        """Return True if the hydrometer is available (present in coordinator data)."""
        return self._mac_id in self.coordinator.data and super().available
