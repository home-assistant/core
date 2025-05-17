"""Support for Hue binary sensors."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .bridge import HueConfigEntry
from .v1.binary_sensor import async_setup_entry as setup_entry_v1
from .v2.binary_sensor import async_setup_entry as setup_entry_v2


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    bridge = config_entry.runtime_data
    if bridge.api_version == 1:
        await setup_entry_v1(hass, config_entry, async_add_entities)
    else:
        await setup_entry_v2(hass, config_entry, async_add_entities)
