"""The PEGELONLINE base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PegelOnlineDataUpdateCoordinator


class PegelOnlineEntity(CoordinatorEntity[PegelOnlineDataUpdateCoordinator]):
    """Representation of a PEGELONLINE entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PegelOnlineDataUpdateCoordinator) -> None:
        """Initialize a PEGELONLINE entity."""
        super().__init__(coordinator)
        self.station = coordinator.station
        self._attr_extra_state_attributes = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.station.uuid)},
            name=f"{self.station.name} {self.station.water_name}",
            manufacturer=self.station.agency,
            configuration_url=self.station.base_data_url,
            entry_type=DeviceEntryType.SERVICE,
        )
