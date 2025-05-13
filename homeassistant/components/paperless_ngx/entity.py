"""Paperless-ngx base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import PaperlessConfigEntry, PaperlessData
from .const import DOMAIN


class PaperlessEntity(Entity):
    """Defines a base Paperless-ngx entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(
        self,
        data: PaperlessData,
        entry: PaperlessConfigEntry,
    ) -> None:
        """Initialize the Paperless-ngx entity."""
        self.client = data.client
        self.inbox_tags = data.inbox_tags
        self.entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Paperless-ngx instance."""

        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={
                (
                    DOMAIN,
                    self.entry.entry_id,
                )
            },
            manufacturer="Paperless-ngx",
            name="Paperless-ngx",
            sw_version=self.client.host_version,
            configuration_url=self.client.base_url,
        )
