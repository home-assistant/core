"""Support for MQTT lights."""
from __future__ import annotations

import functools
from typing import Any

import voluptuous as vol

from homeassistant.components import light
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from ..mixins import async_setup_entry_helper, warn_for_legacy_schema
from .schema import CONF_SCHEMA, MQTT_LIGHT_SCHEMA_SCHEMA
from .schema_basic import (
    DISCOVERY_SCHEMA_BASIC,
    PLATFORM_SCHEMA_BASIC,
    PLATFORM_SCHEMA_MODERN_BASIC,
    async_setup_entity_basic,
)
from .schema_json import (
    DISCOVERY_SCHEMA_JSON,
    PLATFORM_SCHEMA_JSON,
    PLATFORM_SCHEMA_MODERN_JSON,
    async_setup_entity_json,
)
from .schema_template import (
    DISCOVERY_SCHEMA_TEMPLATE,
    PLATFORM_SCHEMA_MODERN_TEMPLATE,
    PLATFORM_SCHEMA_TEMPLATE,
    async_setup_entity_template,
)


def validate_mqtt_light_discovery(config_value: dict[str, Any]) -> ConfigType:
    """Validate MQTT light schema for."""
    schemas = {
        "basic": DISCOVERY_SCHEMA_BASIC,
        "json": DISCOVERY_SCHEMA_JSON,
        "template": DISCOVERY_SCHEMA_TEMPLATE,
    }
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


def validate_mqtt_light(config_value: dict[str, Any]) -> ConfigType:
    """Validate MQTT light schema."""
    schemas = {
        "basic": PLATFORM_SCHEMA_BASIC,
        "json": PLATFORM_SCHEMA_JSON,
        "template": PLATFORM_SCHEMA_TEMPLATE,
    }
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


def validate_mqtt_light_modern(config_value: dict[str, Any]) -> ConfigType:
    """Validate MQTT light schema."""
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

# Configuring MQTT Lights under the light platform key was deprecated in HA Core 2022.6
# Setup for the legacy YAML format was removed in HA Core 2022.12
PLATFORM_SCHEMA = vol.All(
    warn_for_legacy_schema(light.DOMAIN),
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
    """Set up MQTT lights configured under the light platform key (deprecated)."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, light.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: dict | None = None,
) -> None:
    """Set up a MQTT Light."""
    setup_entity = {
        "basic": async_setup_entity_basic,
        "json": async_setup_entity_json,
        "template": async_setup_entity_template,
    }
    await setup_entity[config[CONF_SCHEMA]](
        hass, config, async_add_entities, config_entry, discovery_data
    )
