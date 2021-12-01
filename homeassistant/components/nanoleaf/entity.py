"""Base class for Nanoleaf entity."""

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .hub import NanoleafHub


class NanoleafEntity(Entity):
    """Representation of a Nanoleaf entity."""

    def __init__(self, hub: NanoleafHub) -> None:
        """Initialize an Nanoleaf entity."""
        self._hub = hub
        self._nanoleaf = hub.nanoleaf
        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, hub.nanoleaf.serial_no)},
            manufacturer=hub.nanoleaf.manufacturer,
            model=hub.nanoleaf.model,
            name=hub.nanoleaf.name,
            sw_version=hub.nanoleaf.firmware_version,
            configuration_url=f"http://{hub.nanoleaf.host}",
        )
