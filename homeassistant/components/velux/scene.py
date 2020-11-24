"""Support for VELUX scenes."""
from typing import Any

from homeassistant.components.scene import Scene

from . import _LOGGER
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the scenes for Velux platform."""
    gateway = hass.data[DOMAIN][entry.entry_id]
    entities = [VeluxScene(scene) for scene in gateway.scenes]
    async_add_entities(entities)


class VeluxScene(Scene):
    """Representation of a Velux scene."""

    def __init__(self, scene):
        """Init velux scene."""
        _LOGGER.info("Adding Velux scene: %s", scene)
        self.scene = scene

    @property
    def name(self):
        """Return the name of the scene."""
        return self.scene.name

    @property
    def unique_id(self):
        """Return the unique ID of this scene."""
        return self.scene.scene_id

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self.scene.run(wait_for_completion=False)
