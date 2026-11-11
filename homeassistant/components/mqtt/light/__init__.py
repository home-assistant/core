"""Support for MQTT lights."""

import probatio

from homeassistant.components import light
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from ..const import CONF_SCHEMA
from ..entity import async_setup_entity_entry_helper
from .schema import MQTT_LIGHT_SCHEMA_SCHEMA
from .schema_basic import (
    DISCOVERY_SCHEMA_BASIC,
    PLATFORM_SCHEMA_MODERN_BASIC,
    MqttLight,
)
from .schema_json import (
    DISCOVERY_SCHEMA_JSON,
    PLATFORM_SCHEMA_MODERN_JSON,
    MqttLightJson,
)
from .schema_template import (
    DISCOVERY_SCHEMA_TEMPLATE,
    PLATFORM_SCHEMA_MODERN_TEMPLATE,
    MqttLightTemplate,
)

PARALLEL_UPDATES = 0


DISCOVERY_SCHEMA = probatio.All(
    MQTT_LIGHT_SCHEMA_SCHEMA.extend({}, extra=probatio.ALLOW_EXTRA),
    probatio.TaggedUnion(
        CONF_SCHEMA,
        {
            "basic": DISCOVERY_SCHEMA_BASIC,
            "json": DISCOVERY_SCHEMA_JSON,
            "template": DISCOVERY_SCHEMA_TEMPLATE,
        },
    ),
)

PLATFORM_SCHEMA_MODERN = probatio.All(
    MQTT_LIGHT_SCHEMA_SCHEMA.extend({}, extra=probatio.ALLOW_EXTRA),
    probatio.TaggedUnion(
        CONF_SCHEMA,
        {
            "basic": PLATFORM_SCHEMA_MODERN_BASIC,
            "json": PLATFORM_SCHEMA_MODERN_JSON,
            "template": PLATFORM_SCHEMA_MODERN_TEMPLATE,
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT lights through YAML and through MQTT discovery."""
    async_setup_entity_entry_helper(
        hass,
        config_entry,
        None,
        light.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
        {"basic": MqttLight, "json": MqttLightJson, "template": MqttLightTemplate},
    )
