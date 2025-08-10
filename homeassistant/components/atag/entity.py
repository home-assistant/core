"""The ATAG Integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN
from .coordinator import AtagDataUpdateCoordinator


class AtagEntity(CoordinatorEntity[AtagDataUpdateCoordinator]):
    """Defines a base Atag entity."""

    def __init__(self, coordinator: AtagDataUpdateCoordinator, atag_id: str) -> None:
        """Initialize the Atag entity."""
        super().__init__(coordinator)

        self._id = atag_id
        self._attr_name = DOMAIN.title()
        self._attr_unique_id = f"{coordinator.atag.id}-{atag_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return info for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.atag.id)},
            manufacturer="Atag",
            model="Atag One",
            name="Atag Thermostat",
            sw_version=self.coordinator.atag.apiversion,
        )
