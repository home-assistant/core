"""Base class for Nanoleaf entity."""

from aionanoleaf import Nanoleaf

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class NanoleafEntity(CoordinatorEntity[DataUpdateCoordinator[None]]):
    """Representation of a Nanoleaf entity."""

    _attr_has_entity_name = True

    def __init__(
        self, nanoleaf: Nanoleaf, coordinator: DataUpdateCoordinator[None]
    ) -> None:
        """Initialize a Nanoleaf entity."""
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
