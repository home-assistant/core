"""Models for WLED."""
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
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.data.info.mac_address)},
            name=self.coordinator.data.info.name,
            manufacturer=self.coordinator.data.info.brand,
            model=self.coordinator.data.info.product,
            sw_version=str(self.coordinator.data.info.version),
            configuration_url=f"http://{self.coordinator.wled.host}",
        )
