"""
Support for MQTT vacuums.

For more details about this platform, please refer to the documentation at
https://www.home-assistant.io/components/vacuum.mqtt/
"""
import logging

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN
from homeassistant.components.mqtt import ATTR_DISCOVERY_HASH
from homeassistant.components.mqtt.discovery import (
    MQTT_DISCOVERY_NEW, clear_discovery_hash)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

CONF_SCHEMA = 'schema'
LEGACY = 'legacy'
STATE = 'state'


def validate_mqtt_vacuum(value):
    """Validate MQTT vacuum schema."""
    from . import schema_legacy
    from . import schema_state

    schemas = {
        LEGACY: schema_legacy.PLATFORM_SCHEMA_LEGACY,
        STATE: schema_state.PLATFORM_SCHEMA_STATE,
    }
    return schemas[value[CONF_SCHEMA]](value)


def services_to_strings(services, service_to_string):
    """Convert SUPPORT_* service bitmask to list of service strings."""
    strings = []
    for service in service_to_string:
        if service & services:
            strings.append(service_to_string[service])
    return strings


def strings_to_services(strings, string_to_service):
    """Convert service strings to SUPPORT_* service bitmask."""
    services = 0
    for string in strings:
        services |= string_to_service[string]
    return services


MQTT_VACUUM_SCHEMA = vol.Schema({
    vol.Optional(CONF_SCHEMA, default=LEGACY): vol.All(
        vol.Lower, vol.Any(LEGACY, STATE))
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
    from . import schema_legacy
    from . import schema_state
    setup_entity = {
        LEGACY: schema_legacy.async_setup_entity_legacy,
        STATE: schema_state.async_setup_entity_state,
    }
    await setup_entity[config[CONF_SCHEMA]](
        config, async_add_entities, config_entry, discovery_hash)
