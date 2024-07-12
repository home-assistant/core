"""Base entity for Weheat."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WeheatDataUpdateCoordinator


class WeheatEntity(CoordinatorEntity[WeheatDataUpdateCoordinator]):
    """Defines a base Weheat entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.coordinator.heatpump_id)
            },
            name=self.coordinator.readable_name,
            manufacturer="Weheat",
            model=self.coordinator.model,
            sw_version="",
        )
