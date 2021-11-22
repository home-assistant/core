"""Base class for Nanoleaf entity."""

from aionanoleaf import Nanoleaf

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class NanoleafEntity(Entity):
    """Representation of a Nanoleaf entity."""

    def __init__(self, nanoleaf: Nanoleaf) -> None:
        """Initialize an Nanoleaf entity."""
        self._nanoleaf = nanoleaf
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._nanoleaf.serial_no)},
            manufacturer=self._nanoleaf.manufacturer,
            model=self._nanoleaf.model,
            name=self._nanoleaf.name,
            sw_version=self._nanoleaf.firmware_version,
        )
