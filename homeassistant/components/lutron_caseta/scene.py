"""Support for Lutron Caseta scenes."""
import logging

from homeassistant.components.scene import Scene

from . import LUTRON_CASETA_SMARTBRIDGE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Lutron Caseta lights."""
    entities = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
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

    async def async_activate(self):
        """Activate the scene."""
        self._bridge.activate_scene(self._scene_id)
