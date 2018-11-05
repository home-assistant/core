"""
Support for MQTT lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mqtt/
"""
import logging

from homeassistant.components import mqtt, light
from homeassistant.components.mqtt import ATTR_DISCOVERY_HASH
from homeassistant.components.mqtt.discovery import MQTT_DISCOVERY_NEW
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

from . import schema_basic
from . import schema_json
from . import schema_template

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['mqtt']

PLATFORM_SCHEMA = mqtt.MQTT_RW_PLATFORM_SCHEMA.extend(
    schema_basic.PLATFORM_SCHEMA_BASIC.schema).extend(
        schema_json.PLATFORM_SCHEMA_JSON.schema).extend(
            schema_template.PLATFORM_SCHEMA_TEMPLATE.schema).extend(
                mqtt.MQTT_AVAILABILITY_SCHEMA.schema)


async def async_setup_platform(hass: HomeAssistantType, config: ConfigType,
                               async_add_entities, discovery_info=None):
    """Set up MQTT light through configuration.yaml."""
    await _async_setup_entity(hass, config, async_add_entities)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT light dynamically through MQTT discovery."""
    async def async_discover(discovery_payload):
        """Discover and add a MQTT light."""
        config = PLATFORM_SCHEMA(discovery_payload)
        await _async_setup_entity(hass, config, async_add_entities,
                                  discovery_payload[ATTR_DISCOVERY_HASH])

    async_dispatcher_connect(
        hass, MQTT_DISCOVERY_NEW.format(light.DOMAIN, 'mqtt'),
        async_discover)


async def _async_setup_entity(hass, config, async_add_entities,
                              discovery_hash=None):
    """Set up a MQTT Light."""
    schema = config.get('schema', 'basic')

    if schema == 'basic':
        await schema_basic.async_setup_entity_basic(
            hass, config, async_add_entities, discovery_hash)
    elif schema == 'json':
        await schema_json.async_setup_entity_json(
            hass, config, async_add_entities, discovery_hash)
    elif schema == 'template':
        await schema_template.async_setup_entity_template(
            hass, config, async_add_entities, discovery_hash)
