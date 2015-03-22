"""
homeassistant.components.scene
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Allows users to set and activate scenes within Home Assistant.

A scene is a set of states that describe how you want certain entities to be.
For example, light A should be red with 100 brightness. Light B should be on.

A scene is active if all states of the scene match the real states.

If a scene is manually activated it will store the previous state of the
entities. These will be restored when the state is deactivated manually.

If one of the enties that are being tracked change state on its own, the
old state will not be restored when it is being deactivated.
"""
import logging
from collections import namedtuple

from homeassistant import State
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.state import reproduce_state
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_OFF, STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF)

DOMAIN = 'scene'
DEPENDENCIES = ['group']

ATTR_ACTIVE_REQUESTED = "active_requested"

CONF_ENTITIES = "entities"

SceneConfig = namedtuple('SceneConfig', ['name', 'states'])


def setup(hass, config):
    """ Sets up scenes. """

    logger = logging.getLogger(__name__)

    scene_configs = config.get(DOMAIN)

    if not isinstance(scene_configs, list):
        logger.error('Scene config should be a list of scenes')
        return False

    component = EntityComponent(logger, DOMAIN, hass)

    component.add_entities(Scene(hass, _process_config(scene_config))
                           for scene_config in scene_configs)

    def handle_scene_service(service):
        """ Handles calls to the switch services. """
        target_scenes = component.extract_from_service(service)

        for scene in target_scenes:
            if service.service == SERVICE_TURN_ON:
                scene.turn_on()
            else:
                scene.turn_off()

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_scene_service)
    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_scene_service)

    return True


def _process_config(scene_config):
    """ Process passed in config into a format to work with. """
    name = scene_config.get('name')
    states = {}
    c_entities = dict(scene_config.get(CONF_ENTITIES, {}))

    for entity_id in c_entities:
        if isinstance(c_entities[entity_id], dict):
            state = c_entities[entity_id].pop('state', None)
            attributes = c_entities[entity_id]
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


class Scene(ToggleEntity):
    """ A scene is a group of entities and the states we want them to be. """

    def __init__(self, hass, scene_config):
        self.hass = hass
        self.scene_config = scene_config

        self.is_active = False
        self.prev_states = None
        self.ignore_updates = False

        self.hass.states.track_change(
            self.entity_ids, self.entity_state_changed)

        self.update()

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self.scene_config.name

    @property
    def is_on(self):
        return self.is_active

    @property
    def entity_ids(self):
        """ Entity IDs part of this scene. """
        return self.scene_config.states.keys()

    @property
    def state_attributes(self):
        """ Scene state attributes. """
        return {
            ATTR_ENTITY_ID: list(self.entity_ids),
            ATTR_ACTIVE_REQUESTED: self.prev_states is not None,
        }

    def turn_on(self):
        """ Activates scene. Tries to get entities into requested state. """
        self.prev_states = tuple(self.hass.states.get(entity_id)
                                 for entity_id in self.entity_ids)

        self._reproduce_state(self.scene_config.states.values())

    def turn_off(self):
        """ Deactivates scene and restores old states. """
        if self.prev_states:
            self._reproduce_state(self.prev_states)
            self.prev_states = None

    def entity_state_changed(self, entity_id, old_state, new_state):
        """ Called when an entity part of this scene changes state. """
        if self.ignore_updates:
            return

        # If new state is not what we expect, it can never be active
        if self._state_as_requested(new_state):
            self.update()
        else:
            self.is_active = False
            self.prev_states = None

        self.update_ha_state()

    def update(self):
        """
        Update if the scene is active.

        Will look at each requested state and see if the current entity
        has the same state and has at least the same attributes with the
        same values. The real state can have more attributes.
        """
        self.is_active = all(
            self._state_as_requested(self.hass.states.get(entity_id))
            for entity_id in self.entity_ids)

    def _state_as_requested(self, cur_state):
        """ Returns if given state is as requested. """
        state = self.scene_config.states.get(cur_state and cur_state.entity_id)

        return (cur_state is not None and state.state == cur_state.state and
                all(value == cur_state.attributes.get(key)
                    for key, value in state.attributes.items()))

    def _reproduce_state(self, states):
        """ Wraps reproduce state with Scence specific logic. """
        self.ignore_updates = True
        reproduce_state(self.hass, states, True)
        self.ignore_updates = False

        self.update_ha_state(True)
