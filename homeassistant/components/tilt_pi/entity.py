"""Base entity for Tilt Pi integration."""

from tiltpi import TiltHydrometerData

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import TiltPiDataUpdateCoordinator


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
            connections={(CONNECTION_NETWORK_MAC, hydrometer.mac_id)},
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
        return super().available and self._mac_id in self.coordinator.data
