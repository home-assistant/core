"""
homeassistant.components.scene
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows users to set and activate scenes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scene/
"""
import base64
import logging
import requests

from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_ON)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'powerview_scene'
DEPENDENCIES = ['group']
STATE = 'scening'

HUB_ADDRESS = 'address'

def activate(hass, entity_id=None):
    """ Activate a scene. """
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def setup(hass, config):
    """ Sets up scenes. """

    logger = logging.getLogger(__name__)
    pv_config = config.get(DOMAIN)
    component = EntityComponent(logger, DOMAIN, hass)

    _api_address = "http://" + pv_config[HUB_ADDRESS]
    _scenes = requests.get(_api_address + "/api/scenes/").json()['sceneData']

    component.add_entities(PowerViewScene(hass, pv_scene, _api_address)
                           for pv_scene in _scenes)

    def handle_scene_service(service):
        """ Handles calls to the switch services. """
        target_scenes = component.extract_from_service(service)

        for scene in target_scenes:
            scene.activate()

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_scene_service)

    return True


class PowerViewScene(Entity):
    """ A powerview scene is a group of entities and the states we want them to be. """

    @staticmethod
    def decode_base64(string):
        """returns a utf-8 encoded string converted from a base64 encoding """
        return base64.b64decode(string).decode('utf-8')

    def __init__(self, hass, scene_config, api_address):
        self.hass = hass
        self._name = PowerViewScene.decode_base64(scene_config["name"])
        self._scene_id = str(scene_config["id"])
        self.api_address = api_address
        self.update()

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return STATE

    @property
    def entity_ids(self):
        """ Entity IDs part of this scene. """
        pass

    @property
    def state_attributes(self):
        """ Scene state attributes. """
        pass

    def activate(self):
        """ Activates scene. sends a get request to communicate with the powerview hub """
        requests.get(self.api_address + "/api/scenes?sceneid=" + self._scene_id)
