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


def _convert_states(states):
    """Convert state definitions to State objects."""
    result = {}

    for entity_id in states:
        entity_id = cv.entity_id(entity_id)

        if isinstance(states[entity_id], dict):
            entity_attrs = states[entity_id].copy()
            state = entity_attrs.pop(ATTR_STATE, None)
            attributes = entity_attrs
        else:
            state = states[entity_id]
            attributes = {}

        # YAML translates 'on' to a boolean
        # http://yaml.org/type/bool.html
        if isinstance(state, bool):
            state = STATE_ON if state else STATE_OFF
        elif not isinstance(state, str):
            raise vol.Invalid(f"State for {entity_id} should be a string")

        result[entity_id] = State(entity_id, state, attributes)

    return result


CONF_SCENE_ID = "scene_id"

STATES_SCHEMA = vol.All(dict, _convert_states)

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): HASS_DOMAIN,
        vol.Required(STATES): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_ENTITIES): STATES_SCHEMA,
                }
            ],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

CREATE_SCENE_SCHEMA = vol.Schema(
    {vol.Required(CONF_SCENE_ID): cv.slug, vol.Required(CONF_ENTITIES): STATES_SCHEMA}
)

SERVICE_APPLY = "apply"
SERVICE_CREATE = "create"
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

    async def apply_service(call):
        """Apply a scene."""
        await async_reproduce_state(
            hass, call.data[CONF_ENTITIES].values(), blocking=True, context=call.context
        )

    hass.services.async_register(
        SCENE_DOMAIN,
        SERVICE_APPLY,
        apply_service,
        vol.Schema({vol.Required(CONF_ENTITIES): STATES_SCHEMA}),
    )

    async def create_service(call):
        """Create a scene."""
        scene_config = SCENECONFIG(call.data[CONF_SCENE_ID], call.data[CONF_ENTITIES])
        entity_id = f"{SCENE_DOMAIN}.{scene_config.name}"
        if hass.states.get(entity_id) is not None:
            _LOGGER.warning("The scene %s already exists", entity_id)
            return

        async_add_entities([HomeAssistantScene(hass, scene_config)])

    hass.services.async_register(
        SCENE_DOMAIN, SERVICE_CREATE, create_service, CREATE_SCENE_SCHEMA
    )


def _process_scenes_config(hass, async_add_entities, config):
    """Process multiple scenes and add them."""
    scene_config = config[STATES]

    # Check empty list
    if not scene_config:
        return

    async_add_entities(
        HomeAssistantScene(hass, SCENECONFIG(scene[CONF_NAME], scene[CONF_ENTITIES]))
        for scene in scene_config
    )


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
        return {ATTR_ENTITY_ID: list(self.scene_config.states)}

    async def async_activate(self):
        """Activate scene. Try to get entities into requested state."""
        await async_reproduce_state(
            self.hass,
            self.scene_config.states.values(),
            blocking=True,
            context=self._context,
        )
