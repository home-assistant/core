"""
Platform for the Somfy MyLink device supporting the Synergy JsonRPC API.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/somfy_mylink/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['somfy-mylink-synergy==1.0.2']
CONF_ENTITY_CONFIG = 'entity_config'
CONF_SYSTEM_ID = 'system_id'
CONF_MOVE_TIME = 'move_time'
CONF_REVERSE = 'reverse'
CONF_DEFAULT_MOVE_TIME = 'default_move_time'
CONF_DEFAULT_REVERSE = 'default_reverse'
DATA_SOMFY_MYLINK = 'somfy_mylink_data'
DOMAIN = 'somfy_mylink'
SOMFY_MYLINK_COMPONENTS = [
    'cover', 'scene'
]


def validate_entity_config(values):
    """Validate config entry for CONF_ENTITY."""
    entity_config_schema = vol.Schema({
        vol.Optional(CONF_MOVE_TIME):  vol.Coerce(float),
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
        vol.Optional(CONF_DEFAULT_MOVE_TIME, default=0): vol.Coerce(float),
        vol.Optional(CONF_DEFAULT_REVERSE, default=False): cv.boolean,
        vol.Optional(CONF_ENTITY_CONFIG, default={}): validate_entity_config
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the Demo covers."""
    from somfy_mylink_synergy import SomfyMyLinkSynergy
    host = config[DOMAIN][CONF_HOST]
    port = config[DOMAIN][CONF_PORT]
    system_id = config[DOMAIN][CONF_SYSTEM_ID]
    entity_config = config[DOMAIN].get(CONF_ENTITY_CONFIG, {})
    for default_key in [CONF_DEFAULT_MOVE_TIME, CONF_DEFAULT_REVERSE]:
        config_key = default_key.replace('default_', '')
        if config[DOMAIN].get(default_key, None):
            entity_config.setdefault('default', {})
            entity_config['default'][config_key] = config[DOMAIN][default_key]
    try:
        somfy_mylink = SomfyMyLinkSynergy(system_id, host, port)
    except TimeoutError:
        _LOGGER.error("Unable to connect to the Somfy MyLink device, "
                      "please check your settings")
        return False
    hass.data[DATA_SOMFY_MYLINK] = somfy_mylink
    for component in SOMFY_MYLINK_COMPONENTS:
        hass.async_create_task(async_load_platform(
            hass, component, DOMAIN, entity_config,
            config))
    return True
