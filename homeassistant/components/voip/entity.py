"""VoIP entities."""

from __future__ import annotations

from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr, entity

from .const import DOMAIN


class VoIPEntity(entity.Entity):
    """VoIP entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, device: dr.DeviceEntry) -> None:
        """Initialize VoIP entity."""
        ip_address: str = next(
            item[1] for item in device.identifiers if item[0] == DOMAIN
        )
        self._attr_unique_id = f"{ip_address}-{self.entity_description.key}"
        self._attr_device_info = entity.DeviceInfo(
            identifiers={(DOMAIN, ip_address)},
        )
