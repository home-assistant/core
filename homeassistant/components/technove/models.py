"""Models for TechnoVE."""
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TechnoVEDataUpdateCoordinator


class TechnoVEEntity(CoordinatorEntity[TechnoVEDataUpdateCoordinator]):
    """Defines a base TechnoVE entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TechnoVEDataUpdateCoordinator, key: str) -> None:
        """Initialize a base TechnoVE entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{coordinator.data.info.mac_address}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about this TechnoVE station."""
        data = self.coordinator.data
        return DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, data.info.mac_address)},
            identifiers={(DOMAIN, data.info.mac_address)},
            name=data.info.name,
            manufacturer="TechnoVE",
            model=f"TechnoVE i{data.info.max_station_current}",
            sw_version=data.info.version,
        )
