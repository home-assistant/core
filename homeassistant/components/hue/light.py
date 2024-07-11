"""Support for Hue lights."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import HueBridge
from .const import DOMAIN
from .v1.light import async_setup_entry as setup_entry_v1
from .v2.group import async_setup_entry as setup_groups_entry_v2
from .v2.light import async_setup_entry as setup_entry_v2


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light entities."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]

    if bridge.api_version == 1:
        await setup_entry_v1(hass, config_entry, async_add_entities)
        return
    # v2 setup logic here
    await setup_entry_v2(hass, config_entry, async_add_entities)
    await setup_groups_entry_v2(hass, config_entry, async_add_entities)
