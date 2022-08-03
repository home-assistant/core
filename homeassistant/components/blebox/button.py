"""BleBox button entities implementation."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxEntity, create_blebox_entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox button entry."""
    create_blebox_entities(
        hass, config_entry, async_add_entities, BleBoxButtonEntity, "buttons"
    )


class BleBoxButtonEntity(BleBoxEntity, ButtonEntity):
    """Representation of BleBox buttons."""

    def __init__(self, feature):
        """Initialize a BleBox button feature."""
        super().__init__(feature)
        self._attr_icon = self.get_icon()

    def get_icon(self):
        """Return icon for endpoint."""
        if "up" in self._feature.query_string:
            return "mdi:arrow-up-circle"
        if "down" in self._feature.query_string:
            return "mdi:arrow-down-circle"
        if "fav" in self._feature.query_string:
            return "mdi:heart-circle"
        if "open" in self._feature.query_string:
            return "mdi:arrow-up-circle"
        if "close" in self._feature.query_string:
            return "mdi:arrow-down-circle"
        return ""

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._feature.set()
