"""Base Entity for Hyundai / Kia Connect integration."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRANDS, DOMAIN, REGIONS


class HyundaiKiaConnectEntity(CoordinatorEntity):
    """Class for base entity for Hyundai / Kia Connect integration."""

    @property
    def device_info(self):
        """Return device information to use for this entity."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.data.id)},
            "model": self.coordinator.data.model,
            "manufacturer": f"{BRANDS[self.coordinator.data.brand]} {REGIONS[self.coordinator.data.region]}",
            "name": self.coordinator.data.name,
        }
