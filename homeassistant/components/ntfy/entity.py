"""Base entity for ntfy integration."""

from __future__ import annotations

from yarl import URL

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_TOPIC, DOMAIN
from .coordinator import NtfyConfigEntry


class NtfyBaseEntity(Entity):
    """Base entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

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
            name=subentry.title,
            configuration_url=URL(config_entry.data[CONF_URL]) / self.topic,
            identifiers={(DOMAIN, f"{config_entry.entry_id}_{subentry.subentry_id}")},
            via_device=(DOMAIN, config_entry.entry_id),
        )
        self.ntfy = config_entry.runtime_data.ntfy
        self.config_entry = config_entry
        self.subentry = subentry
