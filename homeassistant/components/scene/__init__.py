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
    ATTR_ENTITY_ID, SERVICE_TURN_ON, CONF_PLATFORM)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

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

    for entry in config:
        if DOMAIN in entry:
            if not any(CONF_PLATFORM in key for key in config[entry]):
                config[entry] = {'platform': 'homeassistant',
                                 'config': config[entry]}

    component = EntityComponent(logger, DOMAIN, hass)

    component.setup(config)

    def handle_scene_service(service):
        """ Handles calls to the switch services. """
        target_scenes = component.extract_from_service(service)

        for scene in target_scenes:
            scene.activate()

    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_scene_service)

    return True


class Scene(Entity):
    """ A scene is a group of entities and the states we want them to be. """

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        raise NotImplementedError

    @property
    def state(self):
        return STATE

    @property
    def entity_ids(self):
        """ Entity IDs part of this scene. """
        return None

    def activate(self):
        """ Activates scene. Tries to get entities into requested state. """
        raise NotImplementedError
