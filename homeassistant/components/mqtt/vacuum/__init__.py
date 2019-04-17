"""
Support for MQTT vacuums.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN
from homeassistant.components.mqtt import ATTR_DISCOVERY_HASH
from homeassistant.components.mqtt.discovery import (
    MQTT_DISCOVERY_NEW, clear_discovery_hash)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

CONF_SCHEMA = 'schema'


def validate_mqtt_vacuum(value):
    """Validate MQTT vacuum schema."""
    from . import schema_basic
    from . import schema_state

    schemas = {
        'basic': schema_basic.PLATFORM_SCHEMA_BASIC,
        'state': schema_state.PLATFORM_SCHEMA_STATE,
    }
    print(value[CONF_SCHEMA])
    return schemas[value[CONF_SCHEMA]](value)


MQTT_VACUUM_SCHEMA = vol.Schema({
    vol.Optional(CONF_SCHEMA, default='basic'): vol.All(
        vol.Lower, vol.Any('basic', 'state'))
})

PLATFORM_SCHEMA = vol.All(MQTT_VACUUM_SCHEMA.extend({
}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up MQTT vacuum through configuration.yaml."""
    await _async_setup_entity(config, async_add_entities,
                              discovery_info)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT vacuum dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT vacuum."""
        try:
            discovery_hash = discovery_payload.pop(ATTR_DISCOVERY_HASH)
            config = PLATFORM_SCHEMA(discovery_payload)
            await _async_setup_entity(config, async_add_entities, config_entry,
                                      discovery_hash)
        except Exception:
            if discovery_hash:
                clear_discovery_hash(hass, discovery_hash)
            raise

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(DOMAIN, 'mqtt'), async_discover)


async def _async_setup_entity(config, async_add_entities, config_entry,
                              discovery_hash=None):
    """Set up the MQTT vacuum."""
    from . import schema_basic
    from . import schema_state
    setup_entity = {
        'basic': schema_basic.async_setup_entity_basic,
        'state': schema_state.async_setup_entity_state,
    }
    await setup_entity[config[CONF_SCHEMA]](
        config, async_add_entities, config_entry, discovery_hash)
