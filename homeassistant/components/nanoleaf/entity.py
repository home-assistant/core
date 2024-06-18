"""Base class for Nanoleaf entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NanoleafCoordinator
from .const import DOMAIN


class NanoleafEntity(CoordinatorEntity[NanoleafCoordinator]):
    """Representation of a Nanoleaf entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NanoleafCoordinator) -> None:
        """Initialize a Nanoleaf entity."""
        super().__init__(coordinator)
        self._nanoleaf = coordinator.nanoleaf
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._nanoleaf.serial_no)},
            manufacturer=self._nanoleaf.manufacturer,
            model=self._nanoleaf.model,
            name=self._nanoleaf.name,
            sw_version=self._nanoleaf.firmware_version,
            configuration_url=f"http://{self._nanoleaf.host}",
        )
