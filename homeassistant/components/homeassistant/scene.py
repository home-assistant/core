"""Allow users to set and activate scenes."""
from collections import namedtuple
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_PLATFORM,
    STATE_OFF,
    STATE_ON,
    SERVICE_RELOAD,
)
from homeassistant.core import State, DOMAIN
from homeassistant import config as conf_util
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_get_integration
from homeassistant.helpers import (
    config_per_platform,
    config_validation as cv,
    entity_platform,
)
from homeassistant.helpers.state import HASS_DOMAIN, async_reproduce_state
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, STATES, Scene

PLATFORM_SCHEMA = vol.Schema(
    {
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
            ],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

SCENECONFIG = namedtuple("SceneConfig", [CONF_NAME, STATES])
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up home assistant scene entries."""
    _process_scenes_config(hass, async_add_entities, config)

    # This platform can be loaded multiple times. Only first time register the service.
    if hass.services.has_service(SCENE_DOMAIN, SERVICE_RELOAD):
        return

    # Store platform for later.
    platform = entity_platform.current_platform.get()

    async def reload_config(call):
        """Reload the scene config."""
        try:
            conf = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(err)
            return

        integration = await async_get_integration(hass, SCENE_DOMAIN)

        conf = await conf_util.async_process_component_config(hass, conf, integration)

        if not conf or not platform:
            return

        await platform.async_reset()

        # Extract only the config for the Home Assistant platform, ignore the rest.
        for p_type, p_config in config_per_platform(conf, SCENE_DOMAIN):
            if p_type != DOMAIN:
                continue

            _process_scenes_config(hass, async_add_entities, p_config)

    hass.helpers.service.async_register_admin_service(
        SCENE_DOMAIN, SERVICE_RELOAD, reload_config
    )


def _process_scenes_config(hass, async_add_entities, config):
    """Process multiple scenes and add them."""
    scene_config = config[STATES]

    # Check empty list
    if not scene_config:
        return

    async_add_entities(
        HomeAssistantScene(hass, _process_scene_config(scene)) for scene in scene_config
    )


def _process_scene_config(scene_config):
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
        return {ATTR_ENTITY_ID: list(self.scene_config.states.keys())}

    async def async_activate(self):
        """Activate scene. Try to get entities into requested state."""
        await async_reproduce_state(self.hass, self.scene_config.states.values(), True)
