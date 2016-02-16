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

DOMAIN = 'pv_scene'
DEPENDENCIES = ['group']
STATE = 'scening'

HUB_ADDRESS = 'address'
CONF_ENTITIES = "entities"


# SceneConfig = namedtuple('SceneConfig', ['name', 'states'])


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


    component.add_entities(PowerViewScene(hass,pv_scene,_api_address)
                           for pv_scene in _scenes)

    def handle_scene_service(service):
        """ Handles calls to the switch services. """
        target_scenes = component.extract_from_service(service)

        for scene in target_scenes:
            scene.activate()

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_scene_service)

    return True


# def _process_config(scene_config):
#     """ Process passed in config into a format to work with. """
#     name = scene_config.get('name')
#
#     states = {}
#     c_entities = dict(scene_config.get(CONF_ENTITIES, {}))
#
#     for entity_id in c_entities:
#         if isinstance(c_entities[entity_id], dict):
#             entity_attrs = c_entities[entity_id].copy()
#             state = entity_attrs.pop('state', None)
#             attributes = entity_attrs
#         else:
#             state = c_entities[entity_id]
#             attributes = {}
#
#         # YAML translates 'on' to a boolean
#         # http://yaml.org/type/bool.html
#         if isinstance(state, bool):
#             state = STATE_ON if state else STATE_OFF
#         else:
#             state = str(state)
#
#         states[entity_id.lower()] = State(entity_id, state, attributes)
#
#     return SceneConfig(name, states)


class PowerViewScene(Entity):
    def decode_base64(str):
        return base64.b64decode(str).decode('utf-8')

    """ A powerview scene is a group of entities and the states we want them to be. """

    def __init__(self, hass, scene_config, api_address):
        self.hass = hass
        self._name = PowerViewScene.decode_base64(scene_config["name"])
        self._scene_id = str(scene_config["id"])
        self.scene_config = scene_config
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
        return self.scene_config.states.keys()

    @property
    def state_attributes(self):
        pass
        """ Scene state attributes. """
        # return {
        #     ATTR_ENTITY_ID: list(self.entity_ids),
        # }

    def activate(self):
        """ Activates scene. Tries to get entities into requested state. """
        # reproduce_state(self.hass, self.scene_config.states.values(), True)
        _stat = requests.get(self.api_address + "/api/scenes?sceneid=" + self._scene_id)
