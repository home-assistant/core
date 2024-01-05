"""Support for Lutron scenes."""
from __future__ import annotations

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LUTRON_CONTROLLER, LUTRON_DEVICES
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
    entities = []
    for scene_data in hass.data[LUTRON_DEVICES]["scene"]:
        (area_name, keypad_name, device, led) = scene_data
        entity = LutronScene(
            area_name, keypad_name, device, led, hass.data[LUTRON_CONTROLLER]
        )
        entities.append(entity)
    async_add_entities(entities, True)


class LutronScene(LutronDevice, Scene):
    """Representation of a Lutron Scene."""

    def __init__(self, area_name, keypad_name, lutron_device, lutron_led, controller):
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
