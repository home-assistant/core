"""Base Entity for Hyundai / Kia Connect integration."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BRANDS, DOMAIN, REGIONS


class HyundaiKiaConnectEntity(CoordinatorEntity):
    """Class for base entity for Hyundai / Kia Connect integration."""

    def __init__(self, coordinator, config_entry: ConfigEntry):
        """Initialize."""
        super().__init__(coordinator)
        self.config_entry = config_entry

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self.config_entry.entry_id

    @property
    def device_info(self):
        """Return device information to use for this entity."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "model": self.coordinator.data.model,
            "manufacturer": f"{BRANDS[self.coordinator.data.brand]} {REGIONS[self.coordinator.data.region]}",
        }
