"""Allow users to set and activate scenes."""
from __future__ import annotations

import logging
from typing import Any, NamedTuple

import voluptuous as vol

from homeassistant import config as conf_util
from homeassistant.components.light import ATTR_TRANSITION
from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, STATES, Scene
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_STATE,
    CONF_ENTITIES,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_PLATFORM,
    SERVICE_RELOAD,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_per_platform,
    config_validation as cv,
    entity_platform,
)
from homeassistant.helpers.state import async_reproduce_state
from homeassistant.loader import async_get_integration


def _convert_states(states):
    """Convert state definitions to State objects."""
    result = {}

    for entity_id, info in states.items():
        entity_id = cv.entity_id(entity_id)

        if isinstance(info, dict):
            entity_attrs = info.copy()
            state = entity_attrs.pop(ATTR_STATE, None)
            attributes = entity_attrs
        else:
            state = info
            attributes = {}

        # YAML translates 'on' to a boolean
        # http://yaml.org/type/bool.html
        if isinstance(state, bool):
            state = STATE_ON if state else STATE_OFF
        elif not isinstance(state, str):
            raise vol.Invalid(f"State for {entity_id} should be a string")

        result[entity_id] = State(entity_id, state, attributes)

    return result


def _ensure_no_intersection(value):
    """Validate that entities and snapshot_entities do not overlap."""
    if (
        CONF_SNAPSHOT not in value
        or CONF_ENTITIES not in value
        or all(
            entity_id not in value[CONF_SNAPSHOT] for entity_id in value[CONF_ENTITIES]
        )
    ):
        return value

    raise vol.Invalid("entities and snapshot_entities must not overlap")


CONF_SCENE_ID = "scene_id"
CONF_SNAPSHOT = "snapshot_entities"
DATA_PLATFORM = "homeassistant_scene"
EVENT_SCENE_RELOADED = "scene_reloaded"
STATES_SCHEMA = vol.All(dict, _convert_states)


PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): HA_DOMAIN,
        vol.Required(STATES): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional(CONF_ID): cv.string,
                        vol.Required(CONF_NAME): cv.string,
                        vol.Optional(CONF_ICON): cv.icon,
                        vol.Required(CONF_ENTITIES): STATES_SCHEMA,
                    }
                )
            ],
        ),
    },
    extra=vol.ALLOW_EXTRA,
)

CREATE_SCENE_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_ENTITIES, CONF_SNAPSHOT),
    _ensure_no_intersection,
    vol.Schema(
        {
            vol.Required(CONF_SCENE_ID): cv.slug,
            vol.Optional(CONF_ENTITIES, default={}): STATES_SCHEMA,
            vol.Optional(CONF_SNAPSHOT, default=[]): cv.entity_ids,
        }
    ),
)

SERVICE_APPLY = "apply"
SERVICE_CREATE = "create"

_LOGGER = logging.getLogger(__name__)


class SceneConfig(NamedTuple):
    """Object for storing scene config."""

    id: str
    name: str
    icon: str
    states: dict


@callback
def scenes_with_entity(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all scenes that reference the entity."""
    if DATA_PLATFORM not in hass.data:
        return []

    platform = hass.data[DATA_PLATFORM]

    return [
        scene_entity.entity_id
        for scene_entity in platform.entities.values()
        if entity_id in scene_entity.scene_config.states
    ]


@callback
def entities_in_scene(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all entities in a scene."""
    if DATA_PLATFORM not in hass.data:
        return []

    platform = hass.data[DATA_PLATFORM]

    entity = platform.entities.get(entity_id)

    if entity is None:
        return []

    return list(entity.scene_config.states)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Home Assistant scene entries."""
    _process_scenes_config(hass, async_add_entities, config)

    # This platform can be loaded multiple times. Only first time register the service.
    if hass.services.has_service(SCENE_DOMAIN, SERVICE_RELOAD):
        return

    # Store platform for later.
    platform = hass.data[DATA_PLATFORM] = entity_platform.async_get_current_platform()

    async def reload_config(call):
        """Reload the scene config."""
        try:
            conf = await conf_util.async_hass_config_yaml(hass)
        except HomeAssistantError as err:
            _LOGGER.error(err)
            return

        integration = await async_get_integration(hass, SCENE_DOMAIN)

        conf = await conf_util.async_process_component_config(hass, conf, integration)

        if not (conf and platform):
            return

        await platform.async_reset()

        # Extract only the config for the Home Assistant platform, ignore the rest.
        for p_type, p_config in config_per_platform(conf, SCENE_DOMAIN):
            if p_type != HA_DOMAIN:
                continue

            _process_scenes_config(hass, async_add_entities, p_config)

        hass.bus.async_fire(EVENT_SCENE_RELOADED, context=call.context)

    hass.helpers.service.async_register_admin_service(
        SCENE_DOMAIN, SERVICE_RELOAD, reload_config
    )

    async def apply_service(call):
        """Apply a scene."""
        reproduce_options = {}

        if ATTR_TRANSITION in call.data:
            reproduce_options[ATTR_TRANSITION] = call.data.get(ATTR_TRANSITION)

        await async_reproduce_state(
            hass,
            call.data[CONF_ENTITIES].values(),
            context=call.context,
            reproduce_options=reproduce_options,
        )

    hass.services.async_register(
        SCENE_DOMAIN,
        SERVICE_APPLY,
        apply_service,
        vol.Schema(
            {
                vol.Optional(ATTR_TRANSITION): vol.All(
                    vol.Coerce(float), vol.Clamp(min=0, max=6553)
                ),
                vol.Required(CONF_ENTITIES): STATES_SCHEMA,
            }
        ),
    )

    async def create_service(call):
        """Create a scene."""
        snapshot = call.data[CONF_SNAPSHOT]
        entities = call.data[CONF_ENTITIES]

        for entity_id in snapshot:
            state = hass.states.get(entity_id)
            if state is None:
                _LOGGER.warning(
                    "Entity %s does not exist and therefore cannot be snapshotted",
                    entity_id,
                )
                continue
            entities[entity_id] = State(entity_id, state.state, state.attributes)

        if not entities:
            _LOGGER.warning("Empty scenes are not allowed")
            return

        scene_config = SceneConfig(None, call.data[CONF_SCENE_ID], None, entities)
        entity_id = f"{SCENE_DOMAIN}.{scene_config.name}"
        old = platform.entities.get(entity_id)
        if old is not None:
            if not old.from_service:
                _LOGGER.warning("The scene %s already exists", entity_id)
                return
            await platform.async_remove_entity(entity_id)
        async_add_entities([HomeAssistantScene(hass, scene_config, from_service=True)])

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
        HomeAssistantScene(
            hass,
            SceneConfig(
                scene.get(CONF_ID),
                scene[CONF_NAME],
                scene.get(CONF_ICON),
                scene[CONF_ENTITIES],
            ),
        )
        for scene in scene_config
    )


class HomeAssistantScene(Scene):
    """A scene is a group of entities and the states we want them to be."""

    def __init__(self, hass, scene_config, from_service=False):
        """Initialize the scene."""
        self.hass = hass
        self.scene_config = scene_config
        self.from_service = from_service

    @property
    def name(self):
        """Return the name of the scene."""
        return self.scene_config.name

    @property
    def icon(self):
        """Return the icon of the scene."""
        return self.scene_config.icon

    @property
    def unique_id(self):
        """Return unique ID."""
        return self.scene_config.id

    @property
    def extra_state_attributes(self):
        """Return the scene state attributes."""
        attributes = {ATTR_ENTITY_ID: list(self.scene_config.states)}
        unique_id = self.unique_id
        if unique_id is not None:
            attributes[CONF_ID] = unique_id
        return attributes

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate scene. Try to get entities into requested state."""
        await async_reproduce_state(
            self.hass,
            self.scene_config.states.values(),
            context=self._context,
            reproduce_options=kwargs,
        )
