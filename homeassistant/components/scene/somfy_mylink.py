"""
Support for Somfy MyLink scenes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/scene.somfy_mylink/
"""
import logging

from homeassistant.components.scene import Scene
from homeassistant.components.somfy_mylink import DATA_SOMFY_MYLINK

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['somfy_mylink']


async def async_setup_platform(hass,
                               config,
                               async_add_entities,
                               discovery_info=None):
    """Discover and configure Somfy MyLink scenes."""
    if discovery_info is None:
        return
    somfy_mylink = hass.data[DATA_SOMFY_MYLINK]
    scene_list = []
    mylink_scenes = await somfy_mylink.scene_list()
    for scene in mylink_scenes['result']:
        _LOGGER.info('Adding Somfy Scene: %s with sceneID %s',
                     scene.get('name'), scene.get('sceneID'))
        scene_data = dict(
            scene_name=scene.get('name'),
            scene_id=scene.get('sceneID')
        )
        scene_list.append(SomfyScene(somfy_mylink, **scene_data))
    async_add_entities(scene_list)


class SomfyScene(Scene):
    """Object for controlling a Somfy scene."""

    def __init__(self, somfy_mylink, scene_name, scene_id):
        """Initialize the scene."""
        self.somfy_mylink = somfy_mylink
        self._name = scene_name
        self._id = scene_id

    async def activate(self):
        """Activate the scene."""
        await self.somfy_mylink.scene_run(self._id)

    @property
    def name(self):
        """Return the name of the scene."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes of the scene."""
        return {'somfy_mylink_scene_id': self._id}
