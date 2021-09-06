"""Models for WLED."""
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WLEDDataUpdateCoordinator


class WLEDEntity(CoordinatorEntity):
    """Defines a base WLED entity."""

    coordinator: WLEDDataUpdateCoordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this WLED device."""
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self.coordinator.data.info.mac_address)},
            ATTR_NAME: self.coordinator.data.info.name,
            ATTR_MANUFACTURER: self.coordinator.data.info.brand,
            ATTR_MODEL: self.coordinator.data.info.product,
            ATTR_SW_VERSION: self.coordinator.data.info.version,
        }
