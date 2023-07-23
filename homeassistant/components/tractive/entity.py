"""A entity class for Tractive integration."""
from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class TractiveEntity(Entity):
    """Tractive entity class."""

    _attr_has_entity_name = True

    def __init__(
        self, user_id: str, trackable: dict[str, Any], tracker_details: dict[str, Any]
    ) -> None:
        """Initialize tracker entity."""
        self._attr_device_info = DeviceInfo(
            configuration_url="https://my.tractive.com/",
            identifiers={(DOMAIN, tracker_details["_id"])},
            name=trackable["details"]["name"],
            manufacturer="Tractive GmbH",
            sw_version=tracker_details["fw_version"],
            model=tracker_details["model_number"],
        )
        self._user_id = user_id
        self._tracker_id = tracker_details["_id"]
        self._trackable = trackable

    @callback
    def handle_status_update(self, event: dict[str, Any]) -> None:
        """Handle status update."""
        self._attr_available = event[self.entity_description.key] is not None
        self.async_write_ha_state()
