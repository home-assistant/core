"""Support for Lutron scenes."""

from __future__ import annotations

from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, LutronController, LutronData
from .entity import LutronKeypadComponent
from .lutron_db import Button


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
        LutronScene(area_name, device_name, button, entry_data.controller, config_entry)
        for area_name, device_name, button in entry_data.scenes
    )


class LutronScene(LutronKeypadComponent, Scene):
    """Representation of a Lutron Scene."""

    _lutron_device: Button

    def __init__(
        self,
        area_name: str,
        device_name: str,
        lutron_device: Button,
        controller: LutronController,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the scene/button."""
        super().__init__(area_name, device_name, lutron_device, controller)
        self._config_entry = config_entry
        self._attr_name = lutron_device.name

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._controller.device_press(
            self._lutron_device.id, self._component_number
        )

    async def async_added_to_hass(self) -> None:  # pylint: disable=hass-missing-super-call
        """Do not register scene as this is only from HA to Lutron."""
        return
