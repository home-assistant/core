"""Base entity for Hikvision integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import HikvisionConfigEntry, HikvisionData
from .const import DOMAIN


class HikvisionEntity(Entity):
    """Base class for Hikvision entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: HikvisionConfigEntry,
        channel: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self._data: HikvisionData = entry.runtime_data
        self._camera = self._data.camera
        self._channel = channel

        # Device info for device registry
        if self._data.device_type == "NVR":
            # NVR channels get their own device linked to the NVR via via_device
            # Get the channel name from channels dict if available
            ch = self._data.channels.get(channel)
            channel_name = (
                ch.name if ch else f"{self._data.device_name} channel {channel}"
            )
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{self._data.device_id}_{channel}")},
                via_device=(DOMAIN, self._data.device_id),
                name=channel_name,
                manufacturer="Hikvision",
                model="NVR channel",
            )
        else:
            # Single camera device
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, self._data.device_id)},
                name=self._data.device_name,
                manufacturer="Hikvision",
                model=self._data.device_type,
            )
