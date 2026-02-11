"""Support for Vera scenes."""

from __future__ import annotations

from typing import Any

import pyvera as veraApi

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .common import ControllerData, get_controller_data
from .const import VERA_ID_FORMAT


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    async_add_entities(
        [VeraScene(device, controller_data) for device in controller_data.scenes], True
    )


class VeraScene(Scene):
    """Representation of a Vera scene entity."""

    def __init__(
        self, vera_scene: veraApi.VeraScene, controller_data: ControllerData
    ) -> None:
        """Initialize the scene."""
        self.vera_scene = vera_scene
        self.controller = controller_data.controller

        self._attr_name = self.vera_scene.name
        # Append device id to prevent name clashes in HA.
        self.vera_id = VERA_ID_FORMAT.format(
            slugify(vera_scene.name), vera_scene.scene_id
        )

    def update(self) -> None:
        """Update the scene status."""
        self.vera_scene.refresh()

    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self.vera_scene.activate()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the scene."""
        return {"vera_scene_id": self.vera_scene.vera_scene_id}
