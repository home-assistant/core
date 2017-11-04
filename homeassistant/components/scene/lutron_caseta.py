"""
Support for Lutron Caseta scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.lutron_caseta/
"""
import logging

from homeassistant.components.scene import Scene
from homeassistant.components.lutron_caseta import LUTRON_CASETA_SMARTBRIDGE

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron_caseta']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Lutron Caseta lights."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    scenes = bridge.get_scenes()
    for scene in scenes:
        dev = LutronCasetaScene(scenes[scene], bridge)
        devs.append(dev)

    add_devices(devs, True)


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

    @property
    def should_poll(self):
        """Return that polling is not necessary."""
        return False

    @property
    def is_on(self):
        """There is no way of detecting if a scene is active (yet)."""
        return False

    def activate(self, **kwargs):
        """Activate the scene."""
        self._bridge.activate_scene(self._scene_id)
