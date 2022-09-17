"""Support for MQTT vacuums."""
from __future__ import annotations

import functools

import voluptuous as vol

from homeassistant.components import vacuum
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from ..mixins import (
    async_discover_yaml_entities,
    async_setup_entry_helper,
    async_setup_platform_helper,
)
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


def validate_mqtt_vacuum_discovery(value):
    """Validate MQTT vacuum schema."""
    schemas = {LEGACY: DISCOVERY_SCHEMA_LEGACY, STATE: DISCOVERY_SCHEMA_STATE}
    return schemas[value[CONF_SCHEMA]](value)


# Configuring MQTT Vacuums under the vacuum platform key is deprecated in HA Core 2022.6
def validate_mqtt_vacuum(value):
    """Validate MQTT vacuum schema (deprecated)."""
    schemas = {LEGACY: PLATFORM_SCHEMA_LEGACY, STATE: PLATFORM_SCHEMA_STATE}
    return schemas[value[CONF_SCHEMA]](value)


def validate_mqtt_vacuum_modern(value):
    """Validate MQTT vacuum modern schema."""
    schemas = {
        LEGACY: PLATFORM_SCHEMA_LEGACY_MODERN,
        STATE: PLATFORM_SCHEMA_STATE_MODERN,
    }
    return schemas[value[CONF_SCHEMA]](value)


DISCOVERY_SCHEMA = vol.All(
    MQTT_VACUUM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum_discovery
)

# Configuring MQTT Vacuums under the vacuum platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    MQTT_VACUUM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum
)

PLATFORM_SCHEMA_MODERN = vol.All(
    MQTT_VACUUM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum_modern
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT vacuum through configuration.yaml."""
    # Deprecated in HA Core 2022.6
    await async_setup_platform_helper(
        hass,
        vacuum.DOMAIN,
        discovery_info or config,
        async_add_entities,
        _async_setup_entity,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT vacuum through configuration.yaml and dynamically through MQTT discovery."""
    # load and initialize platform config from configuration.yaml
    await async_discover_yaml_entities(hass, vacuum.DOMAIN)
    # setup for discovery
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, vacuum.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry | None = None,
    discovery_data: dict | None = None,
) -> None:
    """Set up the MQTT vacuum."""
    setup_entity = {
        LEGACY: async_setup_entity_legacy,
        STATE: async_setup_entity_state,
    }
    await setup_entity[config[CONF_SCHEMA]](
        hass, config, async_add_entities, config_entry, discovery_data
    )
