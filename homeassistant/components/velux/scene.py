"""Support for VELUX scenes."""
from typing import Any

from homeassistant.components.scene import Scene

from . import _LOGGER, DATA_VELUX


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the scenes for Velux platform."""
    entities = [VeluxScene(scene) for scene in hass.data[DATA_VELUX].pyvlx.scenes]
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

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self.scene.run(wait_for_completion=False)
