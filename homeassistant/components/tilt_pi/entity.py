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

    def get_current_hydrometer(self) -> TiltHydrometerData | None:
        """Get current hydrometer data."""
        if not self.coordinator.data:
            return None

        for hydrometer in self.coordinator.data:
            if hydrometer.mac_id == self._mac_id:
                return hydrometer
        return None
