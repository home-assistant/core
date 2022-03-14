"""Base class for Nanoleaf entity."""

from aionanoleaf import Nanoleaf

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class NanoleafEntity(CoordinatorEntity):
    """Representation of a Nanoleaf entity."""

    def __init__(self, nanoleaf: Nanoleaf, coordinator: DataUpdateCoordinator) -> None:
        """Initialize an Nanoleaf entity."""
        super().__init__(coordinator)
        self._nanoleaf = nanoleaf
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, nanoleaf.serial_no)},
            manufacturer=nanoleaf.manufacturer,
            model=nanoleaf.model,
            name=nanoleaf.name,
            sw_version=nanoleaf.firmware_version,
            configuration_url=f"http://{nanoleaf.host}",
        )
