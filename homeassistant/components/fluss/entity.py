"""Base entities for the Fluss+ integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FlussDataUpdateCoordinator


class FlussEntity(CoordinatorEntity[FlussDataUpdateCoordinator]):
    """Base class for Fluss entities without requiring an EntityDescription."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FlussDataUpdateCoordinator,
        device_id: str,
        device: dict | None = None,
    ) -> None:
        """Initialize the entity with a device ID and optional device data."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._device = device
        self._attr_unique_id = f"{device_id}"

    @property
    def device(self) -> dict | None:
        """Return the stored device data or fetch it from the coordinator."""
        if self._device is not None:
            return self._device
        return self.coordinator.data.get(self.device_id)

    @property
    def name(self) -> str:
        """Use the deviceName field for the entity name."""
        return (
            self.device.get("deviceName", super().name) if self.device else super().name
        )

