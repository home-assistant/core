"""Models for Cybro."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_DESCRIPTION, MANUFACTURER, MANUFACTURER_URL
from .coordinator import CybroDataUpdateCoordinator


class CybroEntity(CoordinatorEntity):
    """Defines a base Cybro entity."""

    coordinator: CybroDataUpdateCoordinator

    @property
    def device_info(self):  # -> DeviceInfo:
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
        # return DeviceInfo(
        #    # connections={(CONNECTION_NETWORK_MAC, self.coordinator.unique_id)},
        #    identifiers={(DOMAIN, self.coordinator.unique_id)},
        #    name="Cybro 2/3 PLC",
        #    manufacturer="Cybrotech",
        #    model="Cybro 2/3",
        #    sw_version=str(self.coordinator.data.server_info.server_version),
        #    configuration_url=f"http://{self.coordinator.cybro.host}:{self.coordinator.cybro.port}",
        # )
        # return DeviceInfo(
        #    # entry_type=DeviceEntryType.SERVICE,
        #    identifiers={(DOMAIN, self.coordinator.cybro.nad, self.name)},
        #    manufacturer=MANUFACTURER,
        #    name="Cybro PLC weather station",
        #    model=DEVICE_DESCRIPTION,
        #    sw_version=str(self.coordinator.data.server_info.server_version),
        #    configuration_url=MANUFACTURER_URL,
        # )
