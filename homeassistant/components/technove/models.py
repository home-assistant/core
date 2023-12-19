"""Models for TechnoVE."""
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TechnoVEDataUpdateCoordinator


class TechnoVEEntity(CoordinatorEntity[TechnoVEDataUpdateCoordinator]):
    """Defines a base TechnoVE entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about this TechnoVE station."""
        return DeviceInfo(
            connections={
                (CONNECTION_NETWORK_MAC, self.coordinator.data.info.mac_address)
            },
            identifiers={(DOMAIN, self.coordinator.data.info.mac_address)},
            name=self.coordinator.data.info.name,
            manufacturer="TechnoVE",
            model=f"TechnoVE i{self.coordinator.data.info.max_station_current}",
            sw_version=self.coordinator.data.info.version,
        )
