"""Base entities for the Fluss+ integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FlussDataUpdateCoordinator, FlussDevice


class FlussEntity(CoordinatorEntity[FlussDataUpdateCoordinator]):
    """Base class for Fluss entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FlussDataUpdateCoordinator,
        device: FlussDevice,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device_id = device.device_id
        self._attr_unique_id = device.device_id
        self._attr_device_info = DeviceInfo(
            identifiers={("fluss", device.device_id)},
            name=device.device_name,
            manufacturer="Fluss",
            model="Fluss+ Device",
        )

    @property
    def available(self) -> bool:
        """Return whether the device is reachable."""
        return (
            super().available
            and self.device_id in self.coordinator.data
            and self.coordinator.data[self.device_id].internet_connected
        )

    @property
    def device(self) -> FlussDevice:
        """Return the latest device data from the coordinator."""
        return self.coordinator.data[self.device_id]
