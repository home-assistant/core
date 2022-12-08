"""Support for MQTT vacuums."""
from __future__ import annotations

import functools

import voluptuous as vol

from homeassistant.components import vacuum
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from ..mixins import async_setup_entry_helper, warn_for_legacy_schema
from .schema import CONF_SCHEMA, LEGACY, MQTT_VACUUM_SCHEMA, STATE
from .schema_legacy import (
    DISCOVERY_SCHEMA_LEGACY,
    PLATFORM_SCHEMA_LEGACY,
    PLATFORM_SCHEMA_LEGACY_MODERN,
    async_setup_entity_legacy,
)
from .schema_state import (
    DISCOVERY_SCHEMA_STATE,
    PLATFORM_SCHEMA_STATE,
    PLATFORM_SCHEMA_STATE_MODERN,
    async_setup_entity_state,
)


def validate_mqtt_vacuum_discovery(config_value: ConfigType) -> ConfigType:
    """Validate MQTT vacuum schema."""
    schemas = {LEGACY: DISCOVERY_SCHEMA_LEGACY, STATE: DISCOVERY_SCHEMA_STATE}
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


# Configuring MQTT Vacuums under the vacuum platform key was deprecated in HA Core 2022.6
def validate_mqtt_vacuum(config_value: ConfigType) -> ConfigType:
    """Validate MQTT vacuum schema (deprecated)."""
    schemas = {LEGACY: PLATFORM_SCHEMA_LEGACY, STATE: PLATFORM_SCHEMA_STATE}
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


def validate_mqtt_vacuum_modern(config_value: ConfigType) -> ConfigType:
    """Validate MQTT vacuum modern schema."""
    schemas = {
        LEGACY: PLATFORM_SCHEMA_LEGACY_MODERN,
        STATE: PLATFORM_SCHEMA_STATE_MODERN,
    }
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


DISCOVERY_SCHEMA = vol.All(
    MQTT_VACUUM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum_discovery
)

# Configuring MQTT Vacuums under the vacuum platform key was deprecated in HA Core 2022.6
# Setup for the legacy YAML format was removed in HA Core 2022.12
PLATFORM_SCHEMA = vol.All(
    warn_for_legacy_schema(vacuum.DOMAIN),
)

PLATFORM_SCHEMA_MODERN = vol.All(
    MQTT_VACUUM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum_modern
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT vacuum through configuration.yaml and dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, vacuum.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry,
    discovery_data: DiscoveryInfoType | None = None,
) -> None:
    """Set up the MQTT vacuum."""
    setup_entity = {
        LEGACY: async_setup_entity_legacy,
        STATE: async_setup_entity_state,
    }
    await setup_entity[config[CONF_SCHEMA]](
        hass, config, async_add_entities, config_entry, discovery_data
    )
