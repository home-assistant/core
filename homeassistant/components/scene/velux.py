"""
Support for VELUX scenes.

Connects to VELUX KLF 200 interface

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.velux/
"""
import logging

from homeassistant.components.scene import Scene


DEPENDENCIES = ['velux']
_LOGGER = logging.getLogger(__name__)
DOMAIN = "velux"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup velux scene plattform."""
    if DOMAIN not in hass.data \
            or not hass.data[DOMAIN].initialized:
        _LOGGER.error('No connection to VELUX KLF 200 controller.')
        return False

    entities = []
    for scene in hass.data[DOMAIN].pyvlx.scenes:
        entities.append(VeluxScene(hass, scene))
    add_devices(entities)
    return True


class VeluxScene(Scene):
    """Representation of a velux scene."""

    def __init__(self, hass, scene):
        """Init velux scene."""
        _LOGGER.info("Adding VELUX scene: %s", scene)
        self.hass = hass
        self.scene = scene

    @property
    def name(self):
        """Return the name of the scene."""
        return self.scene.name

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
        self.hass.async_add_job(self.scene.run())
