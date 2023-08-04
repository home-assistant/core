"""The PEGELONLINE base entity."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PegelOnlineDataUpdateCoordinator


class PegelOnlineEntity(CoordinatorEntity[PegelOnlineDataUpdateCoordinator]):
    """Representation of a PEGELONLINE entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(self, coordinator: PegelOnlineDataUpdateCoordinator) -> None:
        """Initialize a PEGELONLINE entity."""
        super().__init__(coordinator)
        self.station = coordinator.station
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information of the entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.station.uuid)},
            name=f"{self.station.name} {self.station.water_name}",
            manufacturer=self.station.agency,
            configuration_url=self.station.base_data_url,
        )
