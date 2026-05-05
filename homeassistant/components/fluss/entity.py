"""Base entities for the Fluss+ integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FlussDataUpdateCoordinator, FlussDevice


def has_open_close_sensor(device: FlussDevice) -> bool:
    """Return whether a device reports an open/close position sensor."""
    return device.open_close_status is not None


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
        """Return if the device is available."""
        return super().available and self.device_id in self.coordinator.data

    @property
    def device(self) -> FlussDevice:
        """Return the stored device data."""
        return self.coordinator.data[self.device_id]
