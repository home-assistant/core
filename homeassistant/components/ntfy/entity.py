"""Base entity for ntfy integration."""

from __future__ import annotations

from yarl import URL

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from . import NtfyConfigEntry
from .const import CONF_TOPIC, DOMAIN


class NtfyBaseEntity(Entity):
    """Base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: NtfyConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the entity."""
        self.topic = subentry.data[CONF_TOPIC]

        self._attr_unique_id = f"{config_entry.entry_id}_{subentry.subentry_id}_{self.entity_description.key}"

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="ntfy LLC",
            model="ntfy",
            name=subentry.data.get(CONF_NAME, self.topic),
            configuration_url=URL(config_entry.data[CONF_URL]) / self.topic,
            identifiers={(DOMAIN, f"{config_entry.entry_id}_{subentry.subentry_id}")},
        )
        self.ntfy = config_entry.runtime_data
        self.config_entry = config_entry
        self.subentry = subentry
