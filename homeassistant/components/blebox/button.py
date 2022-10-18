"""BleBox button entities implementation."""
from __future__ import annotations

import blebox_uniapi.button

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BleBoxEntity, get_blebox_features


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a BleBox button entry."""
    entities: list[BleBoxButtonEntity] = []

    for feature in get_blebox_features(hass, config_entry, "buttons"):
        entities.append(BleBoxButtonEntity(feature))

    async_add_entities(entities, True)


class BleBoxButtonEntity(BleBoxEntity[blebox_uniapi.button.Button], ButtonEntity):
    """Representation of BleBox buttons."""

    def __init__(self, feature: blebox_uniapi.button.Button) -> None:
        """Initialize a BleBox button feature."""
        super().__init__(feature)
        self._attr_icon = self.get_icon()

    def get_icon(self) -> str:
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
