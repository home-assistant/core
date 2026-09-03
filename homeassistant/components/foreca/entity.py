"""Base entity for the Foreca integration."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import ForecaUpdateCoordinator


class ForecaEntity(CoordinatorEntity[ForecaUpdateCoordinator]):
    """Defines a base Foreca entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self.coordinator.device_info
