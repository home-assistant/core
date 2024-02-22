"""The aurora component."""

import logging

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
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
        translation_key: str,
    ) -> None:
        """Initialize the Aurora Entity."""

        super().__init__(coordinator=coordinator)

        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.latitude}_{coordinator.longitude}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="NOAA",
            model="Aurora Visibility Sensor",
        )
