"""
Support for deCONZ scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.deconz/
"""
from homeassistant.components.deconz import (
    DOMAIN as DATA_DECONZ, DATA_DECONZ_ID)
from homeassistant.components.scene import Scene

DEPENDENCIES = ['deconz']


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Old way of setting up deCONZ scenes."""
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up scenes for deCONZ component."""
    scenes = hass.data[DATA_DECONZ].scenes
    entities = []

    for scene in scenes.values():
        entities.append(DeconzScene(scene))
    async_add_devices(entities)


class DeconzScene(Scene):
    """Representation of a deCONZ scene."""

    def __init__(self, scene):
        """Set up a scene."""
        self._scene = scene

    async def async_added_to_hass(self):
        """Subscribe to sensors events."""
        self.hass.data[DATA_DECONZ_ID][self.entity_id] = self._scene.deconz_id

    async def async_activate(self):
        """Activate the scene."""
        await self._scene.async_set_state({})

    @property
    def name(self):
        """Return the name of the scene."""
        return self._scene.full_name
