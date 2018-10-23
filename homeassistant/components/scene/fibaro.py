"""
Support for Fibaro scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.fibaro/
"""
import logging

from homeassistant.util import slugify
from homeassistant.components.scene import Scene
from homeassistant.components.fibaro import (
    FIBARO_CONTROLLER, FIBARO_SCENES, FIBARO_ID_FORMAT)

DEPENDENCIES = ['fibaro']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fibaro scenes."""
    add_entities(
        [FibaroScene(scene, hass.data[FIBARO_CONTROLLER])
         for scene in hass.data[FIBARO_SCENES]], True)


class FibaroScene(Scene):
    """Representation of a Fibaro scene entity."""

    def __init__(self, fibaro_scene, controller):
        """Initialize the scene."""
        self.fibaro_scene = fibaro_scene
        self.controller = controller

        self._name = self.fibaro_scene.name
        # Append device id to prevent name clashes in HA.
        self.fibaro_id = FIBARO_ID_FORMAT.format(
            slugify(fibaro_scene.name), fibaro_scene.scene_id)

    def update(self):
        """Update the scene status."""
        self.fibaro_scene.refresh()

    def activate(self):
        """Activate the scene."""
        self.fibaro_scene.activate()

    @property
    def name(self):
        """Return the name of the scene."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the scene."""
        return {'fibaro_scene_id': self.fibaro_scene.fibaro_scene_id}
