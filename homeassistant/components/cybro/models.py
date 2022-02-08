"""Models for Cybro."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_DESCRIPTION, MANUFACTURER, MANUFACTURER_URL
from .coordinator import CybroDataUpdateCoordinator


class CybroEntity(CoordinatorEntity):
    """Defines a base Cybro entity."""

    coordinator: CybroDataUpdateCoordinator

    @property
    def device_info(self):
        """Return device information about this Cybro device."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (self.coordinator.cybro.nad, self.name)
            },
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": DEVICE_DESCRIPTION,
            "sw_version": self.coordinator.data.server_info.server_version,
            "configuration_url": MANUFACTURER_URL,
        }
