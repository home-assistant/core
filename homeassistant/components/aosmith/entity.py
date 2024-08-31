"""The base entity for the A. O. Smith integration."""


from py_aosmith import AOSmithAPIClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AOSmithCoordinator


class AOSmithEntity(CoordinatorEntity[AOSmithCoordinator]):
    """Base entity for A. O. Smith."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AOSmithCoordinator, junction_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.junction_id = junction_id
        self._attr_device_info = DeviceInfo(
            manufacturer="A. O. Smith",
            name=self.device.get("name"),
            model=self.device.get("model"),
            serial_number=self.device.get("serial"),
            suggested_area=self.device.get("install", {}).get("location"),
            identifiers={(DOMAIN, junction_id)},
            sw_version=self.device.get("data", {}).get("firmwareVersion"),
        )

    @property
    def device(self):
        """Shortcut to get the device status from the coordinator data."""
        return self.coordinator.data.get(self.junction_id)

    @property
    def device_data(self):
        """Shortcut to get the device data within the device status."""
        device = self.device
        return None if device is None else device.get("data", {})

    @property
    def client(self) -> AOSmithAPIClient:
        """Shortcut to get the API client."""
        return self.coordinator.client

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.device_data.get("isOnline") is True
