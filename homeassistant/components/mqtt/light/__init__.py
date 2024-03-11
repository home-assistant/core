"""Support for MQTT lights."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import light
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from ..mixins import async_setup_entity_entry_helper
from .schema import CONF_SCHEMA, MQTT_LIGHT_SCHEMA_SCHEMA
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


def validate_mqtt_light_discovery(config_value: dict[str, Any]) -> ConfigType:
    """Validate MQTT light schema for discovery."""
    schemas = {
        "basic": DISCOVERY_SCHEMA_BASIC,
        "json": DISCOVERY_SCHEMA_JSON,
        "template": DISCOVERY_SCHEMA_TEMPLATE,
    }
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


def validate_mqtt_light_modern(config_value: dict[str, Any]) -> ConfigType:
    """Validate MQTT light schema for setup from configuration.yaml."""
    schemas = {
        "basic": PLATFORM_SCHEMA_MODERN_BASIC,
        "json": PLATFORM_SCHEMA_MODERN_JSON,
        "template": PLATFORM_SCHEMA_MODERN_TEMPLATE,
    }
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


DISCOVERY_SCHEMA = vol.All(
    MQTT_LIGHT_SCHEMA_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA),
    validate_mqtt_light_discovery,
)

PLATFORM_SCHEMA_MODERN = vol.All(
    MQTT_LIGHT_SCHEMA_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA),
    validate_mqtt_light_modern,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT lights through YAML and through MQTT discovery."""
    await async_setup_entity_entry_helper(
        hass,
        config_entry,
        None,
        light.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
        {"basic": MqttLight, "json": MqttLightJson, "template": MqttLightTemplate},
    )
