"""Support for Vera scenes."""

from typing import Any, override

import pyvera as veraApi

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import ControllerData, VeraConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VeraConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    controller_data = entry.runtime_data
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
        self._attr_unique_id = (
            f"{controller_data.config_entry.unique_id}_{vera_scene.scene_id}"
        )

    def update(self) -> None:
        """Update the scene status."""
        self.vera_scene.refresh()

    @override
    def activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        self.vera_scene.activate()

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the scene."""
        return {"vera_scene_id": self.vera_scene.vera_scene_id}
