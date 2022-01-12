"""Base Entity for Hyundai / Kia Connect integration."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRANDS, DOMAIN, REGIONS


class HyundaiKiaConnectEntity(CoordinatorEntity):
    """Class for base entity for Hyundai / Kia Connect integration."""

    def __init__(self, coordinator, vehicle):
        """Initialize the base entity."""
        CoordinatorEntity.__init__(self, coordinator)
        self.vehicle = vehicle

    @property
    def device_info(self):
        """Return device information to use for this entity."""
        return {
            "identifiers": {(DOMAIN, self.vehicle.id)},
            "manufacturer": f"{BRANDS[self.coordinator.vehicle_manager.brand]} {REGIONS[self.coordinator.vehicle_manager.region]}",
            "model": self.vehicle.model,
            "name": self.vehicle.name,
        }
