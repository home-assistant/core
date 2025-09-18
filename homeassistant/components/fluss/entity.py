"""Base entities for the Fluss+ integration."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FlussDataUpdateCoordinator


class FlussEntity(CoordinatorEntity[FlussDataUpdateCoordinator]):
    """Base class for Fluss entities."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: FlussDataUpdateCoordinator,
        device_id: str,
        device: dict,
    ) -> None:
        """Initialize the entity with a device ID and device data."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._device = device
        self._attr_unique_id = f"{device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={("fluss", device_id)},
            name=device.get("deviceName"),
            manufacturer="Fluss",
            model="Fluss+ Device",
        )

    @property
    def device(self) -> dict:
        """Return the stored device data."""
        return self._device
