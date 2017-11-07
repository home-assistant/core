"""
Support for Vera scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.vera/
"""
import logging

from homeassistant.util import slugify
from homeassistant.components.scene import Scene
from homeassistant.components.vera import (
    VERA_CONTROLLER, VERA_SCENES, VERA_ID_FORMAT)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Vera scenes."""
    add_devices(
        VeraScene(scene, VERA_CONTROLLER) for
        scene in VERA_SCENES)


class VeraScene(Scene):
    """Representation of a Vera scene entity."""

    def __init__(self, vera_scene, controller):
        """Initialize the scene."""
        self.vera_scene = vera_scene
        self.controller = controller

        self._name = self.vera_scene.name
        # Append device id to prevent name clashes in HA.
        self.vera_id = VERA_ID_FORMAT.format(
            slugify(vera_scene.name), vera_scene.scene_id)

        self.update()

    def update(self):
        self.vera_scene.refresh()

    def activate(self, **kwargs):
        """Activate the scene."""
        self.vera_scene.activate()

    @property
    def name(self):
        """Return the name of the scene."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the scene."""
        attr = {}

        attr['Vera Scene Id'] = self.vera_scene.vera_scene_id

        return attr

    @property
    def should_poll(self):
        """Return that polling is not necessary."""
        return False

    @property
    def is_on(self):
        """Is the scene active."""
        return self.vera_scene.is_active
