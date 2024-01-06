"""Support for MQTT vacuums."""

# The legacy schema for MQTT vacuum was deprecated with HA Core 2023.8.0
# and will be removed with HA Core 2024.2.0

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import vacuum
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, async_get_hass, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from ..const import DOMAIN
from ..mixins import async_setup_entity_entry_helper
from .schema import CONF_SCHEMA, LEGACY, MQTT_VACUUM_SCHEMA, STATE
from .schema_legacy import (
    DISCOVERY_SCHEMA_LEGACY,
    PLATFORM_SCHEMA_LEGACY_MODERN,
    MqttVacuum,
)
from .schema_state import (
    DISCOVERY_SCHEMA_STATE,
    PLATFORM_SCHEMA_STATE_MODERN,
    MqttStateVacuum,
)

_LOGGER = logging.getLogger(__name__)

MQTT_VACUUM_DOCS_URL = "https://www.home-assistant.io/integrations/vacuum.mqtt/"


# The legacy schema for MQTT vacuum was deprecated with HA Core 2023.8.0
# and will be removed with HA Core 2024.2.0
def warn_for_deprecation_legacy_schema(
    hass: HomeAssistant, config: ConfigType, discovery: bool
) -> None:
    """Warn for deprecation of legacy schema."""
    if config[CONF_SCHEMA] == STATE:
        return

    key_suffix = "discovery" if discovery else "yaml"
    translation_key = f"deprecation_mqtt_legacy_vacuum_{key_suffix}"
    async_create_issue(
        hass,
        DOMAIN,
        translation_key,
        breaks_in_ha_version="2024.2.0",
        is_fixable=False,
        translation_key=translation_key,
        learn_more_url=MQTT_VACUUM_DOCS_URL,
        severity=IssueSeverity.WARNING,
    )
    _LOGGER.warning(
        "Deprecated `legacy` schema detected for MQTT vacuum, expected `state` schema, config found: %s",
        config,
    )


@callback
def validate_mqtt_vacuum_discovery(config_value: ConfigType) -> ConfigType:
    """Validate MQTT vacuum schema."""

    # The legacy schema for MQTT vacuum was deprecated with HA Core 2023.8.0
    # and will be removed with HA Core 2024.2.0

    schemas = {LEGACY: DISCOVERY_SCHEMA_LEGACY, STATE: DISCOVERY_SCHEMA_STATE}
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    hass = async_get_hass()
    warn_for_deprecation_legacy_schema(hass, config, True)
    return config


@callback
def validate_mqtt_vacuum_modern(config_value: ConfigType) -> ConfigType:
    """Validate MQTT vacuum modern schema."""

    # The legacy schema for MQTT vacuum was deprecated with HA Core 2023.8.0
    # and will be removed with HA Core 2024.2.0

    schemas = {
        LEGACY: PLATFORM_SCHEMA_LEGACY_MODERN,
        STATE: PLATFORM_SCHEMA_STATE_MODERN,
    }
    config: ConfigType = schemas[config_value[CONF_SCHEMA]](config_value)
    # The legacy schema for MQTT vacuum was deprecated with HA Core 2023.8.0
    # and will be removed with HA Core 2024.2.0
    hass = async_get_hass()
    warn_for_deprecation_legacy_schema(hass, config, False)
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
        {"legacy": MqttVacuum, "state": MqttStateVacuum},
    )
