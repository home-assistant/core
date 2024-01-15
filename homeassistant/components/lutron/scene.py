"""Support for Lutron scenes."""
from __future__ import annotations

from typing import Any

from pylutron import Button, Led, Lutron

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
            LutronScene(area_name, keypad_name, device, led, entry_data.client)
            for area_name, keypad_name, device, led in entry_data.scenes
        ],
        True,
    )


class LutronScene(LutronDevice, Scene):
    """Representation of a Lutron Scene."""

    _lutron_device: Button

    def __init__(
        self,
        area_name: str,
        keypad_name: str,
        lutron_device: Button,
        lutron_led: Led,
        controller: Lutron,
    ) -> None:
        """Initialize the scene/button."""
        super().__init__(area_name, lutron_device, controller)
        self._keypad_name = keypad_name
        self._led = lutron_led

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self._lutron_device.press()

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return f"{self._area_name} {self._keypad_name}: {self._lutron_device.name}"
