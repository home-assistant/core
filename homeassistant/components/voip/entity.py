"""VoIP entities."""

from __future__ import annotations

from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .devices import VoIPDevice


class VoIPEntity(entity.Entity):
    """VoIP entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: VoIPDevice) -> None:
        """Initialize VoIP entity."""
        self._device = device
        self._attr_unique_id = f"{device.voip_id}-{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.voip_id)},
        )
