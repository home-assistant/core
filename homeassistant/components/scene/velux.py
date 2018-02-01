"""
Support for VELUX scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.velux/
"""
from homeassistant.components.scene import Scene
from homeassistant.components.velux import _LOGGER, DATA_VELUX


DEPENDENCIES = ['velux']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the scenes for velux platform."""
    if DATA_VELUX not in hass.data \
            or not hass.data[DATA_VELUX].initialized:
        return False

    entities = []
    for scene in hass.data[DATA_VELUX].pyvlx.scenes:
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
