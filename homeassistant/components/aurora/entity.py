"""The aurora component."""

import logging

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import AuroraDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class AuroraEntity(CoordinatorEntity[AuroraDataUpdateCoordinator]):
    """Implementation of the base Aurora Entity."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: AuroraDataUpdateCoordinator,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the Aurora Entity."""

        super().__init__(coordinator=coordinator)

        self._attr_name = name
        self._attr_unique_id = f"{coordinator.latitude}_{coordinator.longitude}"
        self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        """Define the device based on name."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(self.unique_id))},
            manufacturer="NOAA",
            model="Aurora Visibility Sensor",
            name=self.coordinator.name,
        )
