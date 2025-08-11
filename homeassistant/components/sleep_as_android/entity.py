"""Base entity for Sleep as Android integration."""

from __future__ import annotations

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from . import SleepAsAndroidConfigEntry
from .const import DOMAIN


class SleepAsAndroidEntity(Entity):
    """Base entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: SleepAsAndroidConfigEntry,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""

        self._attr_unique_id = f"{config_entry.entry_id}_{entity_description.key}"
        self.entity_description = entity_description
        self.webhook_id = config_entry.data[CONF_WEBHOOK_ID]
        self._attr_device_info = DeviceInfo(
            connections={(DOMAIN, config_entry.entry_id)},
            manufacturer="Urbandroid",
            model="Sleep as Android",
            name=config_entry.title,
        )
