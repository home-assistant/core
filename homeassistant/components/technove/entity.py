"""Entity for TechnoVE."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TechnoVEDataUpdateCoordinator


class TechnoVEEntity(CoordinatorEntity[TechnoVEDataUpdateCoordinator]):
    """Defines a base TechnoVE entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TechnoVEDataUpdateCoordinator, key: str) -> None:
        """Initialize a base TechnoVE entity."""
        super().__init__(coordinator)
        info = self.coordinator.data.info
        self._attr_unique_id = f"{info.mac_address}_{key}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, info.mac_address)},
            identifiers={(DOMAIN, info.mac_address)},
            name=info.name,
            manufacturer="TechnoVE",
            model=f"TechnoVE i{info.max_station_current}",
            sw_version=info.version,
        )
