"""Support for MQTT vacuums."""

# The legacy schema for MQTT vacuum was deprecated with HA Core 2023.8.0
# and will be removed with HA Core 2024.2.0

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import vacuum
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from ..mixins import async_setup_entity_entry_helper
from .schema import CONF_SCHEMA, MQTT_VACUUM_SCHEMA, STATE
from .schema_state import (
    DISCOVERY_SCHEMA_STATE,
    PLATFORM_SCHEMA_STATE_MODERN,
    MqttStateVacuum,
)

_LOGGER = logging.getLogger(__name__)

MQTT_VACUUM_DOCS_URL = "https://www.home-assistant.io/integrations/vacuum.mqtt/"


@callback
def validate_mqtt_vacuum_discovery(config_value: ConfigType) -> ConfigType:
    """Validate MQTT vacuum schema."""
    schemas = {STATE: DISCOVERY_SCHEMA_STATE}
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


@callback
def validate_mqtt_vacuum_modern(config_value: ConfigType) -> ConfigType:
    """Validate MQTT vacuum modern schema."""
    schemas = {
        STATE: PLATFORM_SCHEMA_STATE_MODERN,
    }
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    return config


DISCOVERY_SCHEMA = vol.All(
    MQTT_VACUUM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum_discovery
)

PLATFORM_SCHEMA_MODERN = vol.All(
    MQTT_VACUUM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum_modern
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT vacuum through YAML and through MQTT discovery."""
    await async_setup_entity_entry_helper(
        hass,
        config_entry,
        None,
        vacuum.DOMAIN,
        async_add_entities,
        DISCOVERY_SCHEMA,
        PLATFORM_SCHEMA_MODERN,
        {"state": MqttStateVacuum},
    )
