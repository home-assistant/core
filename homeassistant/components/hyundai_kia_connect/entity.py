"""Base Entity for Hyundai / Kia Connect integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRANDS, DOMAIN, REGIONS


class HyundaiKiaConnectEntity(CoordinatorEntity):
    """Class for base entity for Hyundai / Kia Connect integration."""

    def __init__(self, coordinator, config_entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._unique_id = self.coordinator.data.id

    @property
    def device_info(self):
        """Return device information to use for this entity."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "model": self.coordinator.data.model,
            "manufacturer": f"{BRANDS[self.coordinator.data.brand]} {REGIONS[self.coordinator.data.region]}",
        }
