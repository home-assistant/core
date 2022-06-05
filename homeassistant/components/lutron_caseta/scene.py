"""Support for Lutron Caseta scenes."""
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BRIDGE_LEAP, DOMAIN as CASETA_DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron Caseta scene platform.

    Adds scenes from the Caseta bridge associated with the config_entry as
    scene entities.
    """
    data = hass.data[CASETA_DOMAIN][config_entry.entry_id]
    bridge = data[BRIDGE_LEAP]
    scenes = bridge.get_scenes()
    async_add_entities(LutronCasetaScene(scenes[scene], bridge) for scene in scenes)


class LutronCasetaScene(Scene):
    """Representation of a Lutron Caseta scene."""

    def __init__(self, scene, bridge):
        """Initialize the Lutron Caseta scene."""
        self._attr_name = scene["name"]
        self._scene_id = scene["scene_id"]
        self._bridge = bridge

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        await self._bridge.activate_scene(self._scene_id)
