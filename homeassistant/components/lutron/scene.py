"""Support for Lutron scenes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, LutronData
from .aiolip import Button, LutronController
from .entity import LutronKeypadComponent


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron scene platform.

    Adds scenes from the Main Repeater associated with the config_entry as
    scene entities.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LutronScene(button, entry_data.controller) for button in entry_data.scenes
    )


class LutronScene(LutronKeypadComponent, Scene):
    """Representation of a Lutron Scene."""

    _lutron_device: Button

    def __init__(
        self,
        lutron_device: Button,
        controller: LutronController,
    ) -> None:
        """Initialize the scene/button."""
        super().__init__(lutron_device, controller)
        self._attr_name = self.name

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._execute_device_command(self._lutron_device.press)

    async def async_added_to_hass(self) -> None:  # pylint: disable=hass-missing-super-call
        """Do not register scene as this is only from HA to Lutron."""
        return
