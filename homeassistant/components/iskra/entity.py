"""Base entity for Iskra devices."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import IskraDataUpdateCoordinator


class IskraEntity(CoordinatorEntity[IskraDataUpdateCoordinator]):
    """Representation a base Iskra device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IskraDataUpdateCoordinator) -> None:
        """Initialize the Iskra device."""
        super().__init__(coordinator)
        self.device = coordinator.device
        gateway = self.device.parent_device

        if gateway is not None:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.device.serial)},
                manufacturer=MANUFACTURER,
                model=self.device.model,
                name=self.device.model,
                sw_version=self.device.fw_version,
                serial_number=self.device.serial,
                via_device=(DOMAIN, gateway.serial),
            )
        else:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self.device.serial)},
                manufacturer=MANUFACTURER,
                model=self.device.model,
                sw_version=self.device.fw_version,
                serial_number=self.device.serial,
            )
