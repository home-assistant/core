"""Base entity for the Elgato integration."""

from elgato import Elgato, Info

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN


class ElgatoEntity(Entity):
    """Defines an Elgato entity."""

    def __init__(self, client: Elgato, info: Info) -> None:
        """Initialize an Elgato entity."""
        self.client = client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.serial_number)},
            manufacturer="Elgato",
            model=info.product_name,
            name=info.product_name,
            sw_version=f"{info.firmware_version} ({info.firmware_build_number})",
        )
