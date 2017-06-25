"""
Support for VELUX scenes.

Connects to VELUX KLF 200 interface

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.velux/
"""
import logging

from homeassistant.components.scene import Scene
import homeassistant.components.velux as velux_component


DEPENDENCIES = ['velux']
_LOGGER = logging.getLogger(__name__)
DOMAIN = "velux"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup velux scene platt form """

    if velux_component.VELUX_MODULE is None \
            or not velux_component.VELUX_MODULE.initialized:
        _LOGGER.error('A connection has not been made to the VELUX KLF 200 controller.')
        return False

    entities = []
    for scene in velux_component.VELUX_MODULE.pyvlx.scenes:
        entities.append(VeluxScene(hass, scene))
    add_devices(entities)
    return True




class VeluxScene(Scene):
    """Representation of a Velux scene."""

    def __init__(self, hass, scene):
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
        """There is no way of detecting if a scene is active within VELUX KLF 200 (yet)"""
        return False


    def activate(self, **kwargs):
        """Activate the scene."""
        self.hass.async_add_job(self.scene.run())
