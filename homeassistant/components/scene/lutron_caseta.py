"""
Support for Lutron Caseta scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.lutron_caseta/
"""
import asyncio
import logging

from homeassistant.components.lutron_caseta import LUTRON_CASETA_SMARTBRIDGE
from homeassistant.components.scene import Scene

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron_caseta']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Lutron Caseta lights."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    scenes = bridge.get_scenes()
    for scene in scenes:
        dev = LutronCasetaScene(scenes[scene], bridge)
        devs.append(dev)

    async_add_devices(devs, True)


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

    @asyncio.coroutine
    def async_activate(self):
        """Activate the scene."""
        self._bridge.activate_scene(self._scene_id)
