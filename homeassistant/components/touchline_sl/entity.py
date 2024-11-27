"""Base class for Touchline SL zone entities."""

from pytouchlinesl import Zone

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TouchlineSLModuleCoordinator


class TouchlineSLZoneEntity(CoordinatorEntity[TouchlineSLModuleCoordinator]):
    """Defines a base Touchline SL zone entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TouchlineSLModuleCoordinator, zone_id: int) -> None:
        """Initialize touchline entity."""
        super().__init__(coordinator)
        self.zone_id = zone_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(zone_id))},
            name=self.zone.name,
            manufacturer="Roth",
            via_device=(DOMAIN, coordinator.data.module.id),
            model="zone",
            suggested_area=self.zone.name,
        )

    @property
    def zone(self) -> Zone:
        """Return the device object from the coordinator data."""
        return self.coordinator.data.zones[self.zone_id]

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.zone_id in self.coordinator.data.zones
