"""VoIP entities."""

from __future__ import annotations

from homeassistant.components.assist_satellite import AssistSatelliteState
from homeassistant.helpers import entity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .devices import VoIPDevice


class VoIPEntity(entity.Entity):
    """VoIP entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_state = AssistSatelliteState.LISTENING_WAKE_WORD

    def __init__(self, voip_device: VoIPDevice) -> None:
        """Initialize VoIP entity."""
        self.voip_device = voip_device
        self._attr_unique_id = f"{voip_device.voip_id}-{self.entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, voip_device.voip_id)},
        )
