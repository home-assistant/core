"""Support for Lutron Caseta scenes."""
from typing import Any

from homeassistant.components.scene import Scene

from . import DOMAIN as CASETA_DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Lutron Caseta scene platform.

    Adds scenes from the Caseta bridge associated with the config_entry as
    scene entities.
    """

    entities = []
    bridge = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    scenes = bridge.get_scenes()

    for scene in scenes:
        entity = LutronCasetaScene(scenes[scene], bridge)
        entities.append(entity)

    async_add_entities(entities, True)


class LutronCasetaScene(Scene):
    """Representation of a Lutron Caseta scene."""

    def __init__(self, scene, bridge):
        """Initialize the Lutron Caseta scene."""
        self._scene_name = scene["name"]
        self._scene_id = scene["scene_id"]
        self._bridge = bridge

    @property
    def name(self):
        """Return the name of the scene."""
        return self._scene_name

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._bridge.activate_scene(self._scene_id)
