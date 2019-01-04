"""
Support for Fibaro scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.fibaro/
"""
import logging

from homeassistant.components.scene import (
    Scene)
from homeassistant.components.fibaro import (
    FIBARO_CONTROLLER, FIBARO_DEVICES, FibaroDevice)

DEPENDENCIES = ['fibaro']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Perform the setup for Fibaro scenes."""
    if discovery_info is None:
        return

    async_add_entities(
        [FibaroScene(scene, hass.data[FIBARO_CONTROLLER])
         for scene in hass.data[FIBARO_DEVICES]['scene']], True)


class FibaroScene(FibaroDevice, Scene):
    """Representation of a Fibaro scene entity."""

    def activate(self):
        """Activate the scene."""
        self.fibaro_device.start()
