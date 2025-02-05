"""The entity for the Youless integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YouLessCoordinator


class YouLessEntity(CoordinatorEntity[YouLessCoordinator]):
    """Base entity for YouLess."""

    def __init__(
        self, coordinator: YouLessCoordinator, device_group: str, device_name: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.device = coordinator.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_group)},
            manufacturer="YouLess",
            model=self.device.model,
            translation_key=device_name,
            sw_version=self.device.firmware_version,
        )
