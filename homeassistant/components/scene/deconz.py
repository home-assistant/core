"""
Support for deCONZ scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.deconz/
"""

import asyncio
import logging

from homeassistant.components.deconz import DOMAIN
from homeassistant.components.scene import Scene

DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up scenes for deCONZ component."""
    if discovery_info is None:
        return False

    scenes = hass.data[DOMAIN].scenes
    entities = []

    for scene in scenes.values():
        entities.append(DeconzScene(scene))
    async_add_devices(entities)


class DeconzScene(Scene):
    """Representation of a deCONZ scene."""

    def __init__(self, scene):
        """Setup scene."""
        self._scene = scene

    @asyncio.coroutine
    def async_activate(self, **kwargs):
        """Activate the scene."""
        yield from self._scene.async_set_state({})

    @property
    def name(self):
        """Return the name of the scene."""
        return self._scene.full_name

    @property
    def should_poll(self):
        """No polling needed."""
        return False
