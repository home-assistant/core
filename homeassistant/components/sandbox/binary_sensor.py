"""Binary sensor platform for the Sandbox integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_SANDBOX


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sandbox binary sensor entities."""
    sandbox_data = hass.data[DATA_SANDBOX]
    sandbox_id = config_entry.entry_id

    manager = sandbox_data.entity_managers.get(sandbox_id)
    if manager is not None:
        manager.register_platform_callback("binary_sensor", async_add_entities)
