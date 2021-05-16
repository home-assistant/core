"""Support for VELUX scenes."""
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import _LOGGER
from .const import CONFIG_KEY_MODULE, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the scenes for Velux platform."""
    veluxModule = hass.data[DOMAIN][entry.entry_id][CONFIG_KEY_MODULE]
    entities = [VeluxScene(scene) for scene in veluxModule.pyvlx.scenes]
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
