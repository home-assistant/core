"""The ATAG Integration."""

from pyatag import AtagOne

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import DOMAIN


class AtagEntity(CoordinatorEntity[DataUpdateCoordinator[AtagOne]]):
    """Defines a base Atag entity."""

    def __init__(
        self, coordinator: DataUpdateCoordinator[AtagOne], atag_id: str
    ) -> None:
        """Initialize the Atag entity."""
        super().__init__(coordinator)

        self._id = atag_id
        self._attr_name = DOMAIN.title()
        self._attr_unique_id = f"{coordinator.data.id}-{atag_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return info for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.id)},
            manufacturer="Atag",
            model="Atag One",
            name="Atag Thermostat",
            sw_version=self.coordinator.data.apiversion,
        )
