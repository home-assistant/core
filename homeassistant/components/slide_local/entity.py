"""Entities for slide_local integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SlideCoordinator


class SlideEntity(CoordinatorEntity[SlideCoordinator]):
    """Base class of a Slide local API cover."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SlideCoordinator,
    ) -> None:
        """Initialize the Slide device."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            manufacturer="Innovation in Motion",
            identifiers={(DOMAIN, coordinator.data["mac"])},
            name=coordinator.data["device_name"],
            sw_version=coordinator.api_version,
        )

    @property
    def available(self) -> bool:
        """Return False if state is not available."""
        return super().available and "pos" in self.coordinator.data
