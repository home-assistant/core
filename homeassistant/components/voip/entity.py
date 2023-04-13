"""VoIP entities."""

from __future__ import annotations

from homeassistant.helpers import entity
from .const import DOMAIN


class VoIPEntity(entity.Entity):
    """VoIP entity."""

    _attr_has_entity_name = True

    def __init__(self, ip_address: str) -> None:
        """Initialize VoIP entity."""
        self._ip_address = ip_address
        self._attr_device_info = entity.DeviceInfo(
            identifiers={(DOMAIN, ip_address)},
            name=ip_address,
            configuration_url=f"http://{ip_address}",
        )
