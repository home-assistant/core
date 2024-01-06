"""Support for Lutron scenes."""
from __future__ import annotations

from typing import Any

from pylutron import Button, Lutron, LutronEntity

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, LutronData
from .entity import LutronDevice


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron scene platform.

    Adds scenes from the Main Repeater associated with the config_entry as
    scene entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [
            LutronScene(area_name, keypad_name, device, entry_data.client)
            for area_name, keypad_name, device, led in entry_data.scenes
        ],
        True,
    )


class LutronScene(LutronDevice, Scene):
    """Representation of a Lutron Scene."""

    _lutron_device: Button
    _attr_name = None

    def __init__(
        self,
        area_name: str,
        keypad_name: str,
        lutron_device: LutronEntity,
        controller: Lutron,
    ) -> None:
        """Initialize the scene/button."""
        super().__init__(area_name, lutron_device, controller)
        self._keypad_name = keypad_name

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self._lutron_device.press()
