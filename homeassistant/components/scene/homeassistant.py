"""
Allow users to set and activate scenes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scene/
"""
import asyncio
from collections import namedtuple

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.scene import Scene, STATES
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_STATE, CONF_ENTITIES, CONF_NAME, CONF_PLATFORM,
    STATE_OFF, STATE_ON)
from homeassistant.core import State
from homeassistant.helpers.state import async_reproduce_state, HASS_DOMAIN

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): HASS_DOMAIN,
    vol.Required(STATES): vol.All(
        cv.ensure_list,
        [
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_ENTITIES): {
                    cv.entity_id: vol.Any(str, bool, dict)
                },
            }
        ]
    ),
}, extra=vol.ALLOW_EXTRA)

SCENECONFIG = namedtuple('SceneConfig', [CONF_NAME, STATES])


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities,
                         discovery_info=None):
    """Set up home assistant scene entries."""
    scene_config = config.get(STATES)

    async_add_entities(HomeAssistantScene(
        hass, _process_config(scene)) for scene in scene_config)
    return True


def _process_config(scene_config):
    """Process passed in config into a format to work with.

    Async friendly.
    """
    name = scene_config.get(CONF_NAME)

    states = {}
    c_entities = dict(scene_config.get(CONF_ENTITIES, {}))

    for entity_id in c_entities:
        if isinstance(c_entities[entity_id], dict):
            entity_attrs = c_entities[entity_id].copy()
            state = entity_attrs.pop(ATTR_STATE, None)
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

    return SCENECONFIG(name, states)


class HomeAssistantScene(Scene):
    """A scene is a group of entities and the states we want them to be."""

    def __init__(self, hass, scene_config):
        """Initialize the scene."""
        self.hass = hass
        self.scene_config = scene_config

    @property
    def name(self):
        """Return the name of the scene."""
        return self.scene_config.name

    @property
    def device_state_attributes(self):
        """Return the scene state attributes."""
        return {
            ATTR_ENTITY_ID: list(self.scene_config.states.keys()),
        }

    @asyncio.coroutine
    def async_activate(self):
        """Activate scene. Try to get entities into requested state."""
        yield from async_reproduce_state(
            self.hass, self.scene_config.states.values(), True)
