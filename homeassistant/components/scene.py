"""
homeassistant.components.scene
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows users to set and activate scenes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scene/
"""
import logging
from collections import namedtuple

from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_OFF, STATE_ON)
from homeassistant.core import State
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.state import reproduce_state

DOMAIN = 'scene'
DEPENDENCIES = ['group']
STATE = 'scening'

CONF_ENTITIES = "entities"

SceneConfig = namedtuple('SceneConfig', ['name', 'states'])


def activate(hass, entity_id=None):
    """ Activate a scene. """
    data = {}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def setup(hass, config):
    """ Sets up scenes. """

    logger = logging.getLogger(__name__)

    scene_configs = config.get(DOMAIN)

    if not isinstance(scene_configs, list) or \
       any(not isinstance(item, dict) for item in scene_configs):
        logger.error('Scene config should be a list of dictionaries')
        return False

    component = EntityComponent(logger, DOMAIN, hass)

    component.add_entities(Scene(hass, _process_config(scene_config))
                           for scene_config in scene_configs)

    def handle_scene_service(service):
        """ Handles calls to the switch services. """
        target_scenes = component.extract_from_service(service)

        for scene in target_scenes:
            scene.activate()

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_scene_service)

    return True


def _process_config(scene_config):
    """ Process passed in config into a format to work with. """
    name = scene_config.get('name')

    states = {}
    c_entities = dict(scene_config.get(CONF_ENTITIES, {}))

    for entity_id in c_entities:
        if isinstance(c_entities[entity_id], dict):
            entity_attrs = c_entities[entity_id].copy()
            state = entity_attrs.pop('state', None)
            attributes = entity_attrs
        else:
            state = c_entities[entity_id]
            attributes = {}

        # YAML translates 'on' to a boolean
        # http://yaml.org/type/bool.html
        if isinstance(state, bool):
            state = STATE_ON if state else STATE_OFF
        else:
            state = str(state)

        states[entity_id.lower()] = State(entity_id, state, attributes)

    return SceneConfig(name, states)


class Scene(Entity):
    """ A scene is a group of entities and the states we want them to be. """

    def __init__(self, hass, scene_config):
        self.hass = hass
        self.scene_config = scene_config

        self.update()

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self.scene_config.name

    @property
    def state(self):
        return STATE

    @property
    def entity_ids(self):
        """ Entity IDs part of this scene. """
        return self.scene_config.states.keys()

    @property
    def state_attributes(self):
        """ Scene state attributes. """
        return {
            ATTR_ENTITY_ID: list(self.entity_ids),
        }

    def activate(self):
        """ Activates scene. Tries to get entities into requested state. """
        reproduce_state(self.hass, self.scene_config.states.values(), True)
