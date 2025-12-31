"""Button platform for Elke27."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import device_info_for_entry
from .hub import Elke27Hub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 refresh button."""
    hub: Elke27Hub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([Elke27RefreshInventoryButton(hub, entry)])


class Elke27RefreshInventoryButton(ButtonEntity):
    """Button to refresh inventory from the panel."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_inventory"

    def __init__(self, hub: Elke27Hub, entry: ConfigEntry) -> None:
        """Initialize the refresh button."""
        self._hub = hub
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_refresh_inventory"
        self._attr_device_info = device_info_for_entry(hub, entry)

    async def async_press(self) -> None:
        """Request an inventory refresh."""
        await self._hub.async_refresh_inventory()
