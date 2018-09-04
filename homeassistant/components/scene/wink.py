"""
Support for Wink scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.wink/
"""
import asyncio
import logging

from homeassistant.components.scene import Scene
from homeassistant.components.wink import DOMAIN, WinkDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['wink']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Wink platform."""
    import pywink

    for scene in pywink.get_scenes():
        _id = scene.object_id() + scene.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            add_entities([WinkScene(scene, hass)])


class WinkScene(WinkDevice, Scene):
    """Representation of a Wink shortcut/scene."""

    def __init__(self, wink, hass):
        """Initialize the Wink device."""
        super().__init__(wink, hass)
        hass.data[DOMAIN]['entities']['scene'].append(self)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['scene'].append(self)

    def activate(self):
        """Activate the scene."""
        self.wink.activate()
