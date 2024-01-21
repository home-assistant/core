"""Support for Lutron scenes."""
from __future__ import annotations

from typing import Any

from pylutron import Button, Keypad, Lutron

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_IDENTIFIERS, ATTR_VIA_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, LutronData
from .entity import LutronBaseEntity


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
            LutronScene(area_name, keypad, device, entry_data.client)
            for area_name, keypad, device, led in entry_data.scenes
        ],
        True,
    )


class LutronScene(LutronBaseEntity, Scene):
    """Representation of a Lutron Scene."""

    _lutron_device: Button

    def __init__(
        self,
        area_name: str,
        keypad: Keypad,
        lutron_device: Button,
        controller: Lutron,
    ) -> None:
        """Initialize the scene/button."""
        super().__init__(area_name, lutron_device, controller)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, keypad.id)},
            manufacturer="Lutron",
            name=keypad.name,
        )
        self._attr_name = lutron_device.name
        if keypad.type == "MAIN_REPEATER":
            self._attr_device_info[ATTR_IDENTIFIERS].add((DOMAIN, controller.guid))
        else:
            self._attr_device_info[ATTR_VIA_DEVICE] = (DOMAIN, controller.guid)

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self._lutron_device.press()
