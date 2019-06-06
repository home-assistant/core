"""Component for the Somfy MyLink device supporting the Synergy API."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)
CONF_ENTITY_CONFIG = 'entity_config'
CONF_SYSTEM_ID = 'system_id'
CONF_REVERSE = 'reverse'
CONF_DEFAULT_REVERSE = 'default_reverse'
DATA_SOMFY_MYLINK = 'somfy_mylink_data'
DOMAIN = 'somfy_mylink'
SOMFY_MYLINK_COMPONENTS = [
    'cover'
]


def validate_entity_config(values):
    """Validate config entry for CONF_ENTITY."""
    entity_config_schema = vol.Schema({
        vol.Optional(CONF_REVERSE): cv.boolean
    })
    if not isinstance(values, dict):
        raise vol.Invalid('expected a dictionary')
    entities = {}
    for entity_id, config in values.items():
        entity = cv.entity_id(entity_id)
        config = entity_config_schema(config)
        entities[entity] = config
    return entities


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_SYSTEM_ID): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=44100): cv.port,
        vol.Optional(CONF_DEFAULT_REVERSE, default=False): cv.boolean,
        vol.Optional(CONF_ENTITY_CONFIG, default={}): validate_entity_config
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the MyLink platform."""
    from somfy_mylink_synergy import SomfyMyLinkSynergy
    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    system_id = config[DOMAIN][CONF_SYSTEM_ID]
    entity_config = config[DOMAIN][CONF_ENTITY_CONFIG]
    entity_config[CONF_DEFAULT_REVERSE] = config[DOMAIN][CONF_DEFAULT_REVERSE]
    somfy_mylink = SomfyMyLinkSynergy(system_id, host, port)
    hass.data[DATA_SOMFY_MYLINK] = somfy_mylink
    for component in SOMFY_MYLINK_COMPONENTS:
        hass.async_create_task(async_load_platform(
            hass, component, DOMAIN, entity_config,
            config))
    return True
