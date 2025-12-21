"""Support for scenes through the SmartThings cloud API."""

from typing import Any

from pysmartthings import Scene as STScene, SmartThings

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmartThingsConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add lights for a config entry."""
    client = entry.runtime_data.client
    scenes = entry.runtime_data.scenes
    async_add_entities(SmartThingsScene(scene, client) for scene in scenes.values())


class SmartThingsScene(Scene):
    """Define a SmartThings scene."""

    def __init__(self, scene: STScene, client: SmartThings) -> None:
        """Init the scene class."""
        self.client = client
        self._scene = scene
        self._attr_name = scene.name
        self._attr_unique_id = scene.scene_id

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene."""
        await self.client.execute_scene(self._scene.scene_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Get attributes about the state."""
        return {
            "icon": self._scene.icon,
            "color": self._scene.color,
            "location_id": self._scene.location_id,
        }
