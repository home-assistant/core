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
    if DECONZ_DATA in hass.data:
        scenes = hass.data[DECONZ_DATA].scenes
    print('deconz scenes', scenes)
    for _, scene in scenes.items():
        async_add_devices([DeconzScene(scene)])
    print('scene set up done')


class DeconzScene(Scene):
    """Representation of a single LiteJet scene."""

    def __init__(self, scene):
        """Setup sensor and add update callback to get data from websocket."""
        self._scene = scene

    @property
    def name(self):
        """Return the name of the scene."""
        return self._scene._group_name + '_' + self._scene.name
        # return self._name

    @property
    def should_poll(self):
        """Return that polling is not necessary."""
        return False

    @asyncio.coroutine
    def async_activate(self, **kwargs):
        """Activate the scene."""
        print('scene active kwargs', kwargs)
        yield from self._scene.set_state({})
