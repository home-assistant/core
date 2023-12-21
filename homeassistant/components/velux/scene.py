"""Support for VELUX scenes."""
from typing import Any

from pyvlx import PyVLX, Scene as PyvlxScene

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import _LOGGER
from .const import DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the scenes for Velux platform."""
    pyvlx: PyVLX = hass.data[DOMAIN][entry.entry_id]
    entities = [VeluxScene(scene) for scene in pyvlx.scenes]
    async_add_entities(entities)


class VeluxScene(Scene):
    """Representation of a Velux scene."""

    def __init__(self, scene: PyvlxScene) -> None:
        """Init velux scene."""
        _LOGGER.info("Adding Velux scene: %s", scene)
        self.scene: PyvlxScene = scene

    @property
    def name(self) -> str:
        """Return the name of the scene."""
        return self.scene.name

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this cover."""
        return str(self.scene.scene_id)

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self.scene.run(wait_for_completion=False)
