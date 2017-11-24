"""
Support for deCONZ scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.deconz/
"""

import asyncio
import logging

from homeassistant.components.deconz import DECONZ_DATA, DOMAIN
from homeassistant.components.scene import Scene

DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up scenes for the deCONZ platform."""
    scenes = hass.data[DECONZ_DATA].scenes

    for scene in scenes.values():
        async_add_devices([DeconzScene(scene)])


class DeconzScene(Scene):
    """Representation of a single deCONZ scene."""

    def __init__(self, scene):
        """Setup scene."""
        self._scene = scene

    @asyncio.coroutine
    def async_activate(self, **kwargs):
        """Activate the scene."""
        yield from self._scene.set_state({})

    @property
    def name(self):
        """Return the name of the scene."""
        return self._scene.full_name

    @property
    def should_poll(self):
        """No polling needed."""
        return False
