"""Base entity for the Bambu Lab integration."""

from typing import override

from aiobambulab import BambuLabClient

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class BambuLabEntity(Entity):
    """Base class for the entities of a Bambu Lab printer."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, client: BambuLabClient) -> None:
        """Initialize the entity."""
        self._client = client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.serial)},
            manufacturer="Bambu Lab",
            model=client.info.model_name,
            serial_number=client.serial,
            sw_version=client.info.firmware_version,
            hw_version=client.info.hardware_version,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Follow the printer once the entity is added."""
        await super().async_added_to_hass()
        self.async_on_remove(self._client.add_listener(self.async_write_ha_state))

    @override
    @property
    def available(self) -> bool:
        """Return whether the printer is available."""
        return super().available and self._client.available
