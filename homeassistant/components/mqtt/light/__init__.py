"""Support for MQTT lights."""
from __future__ import annotations

import functools

import voluptuous as vol

from homeassistant.components import light
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from ..mixins import (
    async_discover_yaml_entities,
    async_setup_entry_helper,
    async_setup_platform_helper,
    warn_for_legacy_schema,
)
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


def validate_mqtt_light_discovery(value):
    """Validate MQTT light schema for."""
    schemas = {
        "basic": DISCOVERY_SCHEMA_BASIC,
        "json": DISCOVERY_SCHEMA_JSON,
        "template": DISCOVERY_SCHEMA_TEMPLATE,
    }
    return schemas[value[CONF_SCHEMA]](value)


def validate_mqtt_light(value):
    """Validate MQTT light schema."""
    schemas = {
        "basic": PLATFORM_SCHEMA_BASIC,
        "json": PLATFORM_SCHEMA_JSON,
        "template": PLATFORM_SCHEMA_TEMPLATE,
    }
    return schemas[value[CONF_SCHEMA]](value)


def validate_mqtt_light_modern(value):
    """Validate MQTT light schema."""
    schemas = {
        "basic": PLATFORM_SCHEMA_MODERN_BASIC,
        "json": PLATFORM_SCHEMA_MODERN_JSON,
        "template": PLATFORM_SCHEMA_MODERN_TEMPLATE,
    }
    return schemas[value[CONF_SCHEMA]](value)


DISCOVERY_SCHEMA = vol.All(
    MQTT_LIGHT_SCHEMA_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA),
    validate_mqtt_light_discovery,
)

# Configuring MQTT Lights under the light platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    cv.PLATFORM_SCHEMA.extend(MQTT_LIGHT_SCHEMA_SCHEMA.schema, extra=vol.ALLOW_EXTRA),
    validate_mqtt_light,
    warn_for_legacy_schema(light.DOMAIN),
)

PLATFORM_SCHEMA_MODERN = vol.All(
    MQTT_LIGHT_SCHEMA_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA),
    validate_mqtt_light_modern,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT light through configuration.yaml (deprecated)."""
    # Deprecated in HA Core 2022.6
    await async_setup_platform_helper(
        hass,
        light.DOMAIN,
        discovery_info or config,
        async_add_entities,
        _async_setup_entity,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT lights configured under the light platform key (deprecated)."""
    # load and initialize platform config from configuration.yaml
    await async_discover_yaml_entities(hass, light.DOMAIN)
    # setup for discovery
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, light.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up a MQTT Light."""
    setup_entity = {
        "basic": async_setup_entity_basic,
        "json": async_setup_entity_json,
        "template": async_setup_entity_template,
    }
    await setup_entity[config[CONF_SCHEMA]](
        hass, config, async_add_entities, config_entry, discovery_data
    )
