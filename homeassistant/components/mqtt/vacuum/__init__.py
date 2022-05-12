"""Support for MQTT vacuums."""
import functools

import voluptuous as vol

from homeassistant.components import vacuum

from ..mixins import async_setup_entry_helper, async_setup_platform_helper
from .schema import CONF_SCHEMA, LEGACY, MQTT_VACUUM_SCHEMA, STATE
from .schema_legacy import (
    DISCOVERY_SCHEMA_LEGACY,
    PLATFORM_SCHEMA_LEGACY,
    async_setup_entity_legacy,
)
from .schema_state import (
    DISCOVERY_SCHEMA_STATE,
    PLATFORM_SCHEMA_STATE,
    async_setup_entity_state,
)


def validate_mqtt_vacuum_discovery(value):
    """Validate MQTT vacuum schema."""
    schemas = {LEGACY: DISCOVERY_SCHEMA_LEGACY, STATE: DISCOVERY_SCHEMA_STATE}
    return schemas[value[CONF_SCHEMA]](value)


def validate_mqtt_vacuum(value):
    """Validate MQTT vacuum schema."""
    schemas = {LEGACY: PLATFORM_SCHEMA_LEGACY, STATE: PLATFORM_SCHEMA_STATE}
    return schemas[value[CONF_SCHEMA]](value)


DISCOVERY_SCHEMA = vol.All(
    MQTT_VACUUM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum_discovery
)

PLATFORM_SCHEMA = vol.All(
    MQTT_VACUUM_SCHEMA.extend({}, extra=vol.ALLOW_EXTRA), validate_mqtt_vacuum
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up MQTT vacuum through configuration.yaml."""
    await async_setup_platform_helper(
        hass, vacuum.DOMAIN, config, async_add_entities, _async_setup_entity
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up MQTT vacuum dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, vacuum.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass, async_add_entities, config, config_entry=None, discovery_data=None
):
    """Set up the MQTT vacuum."""
    setup_entity = {LEGACY: async_setup_entity_legacy, STATE: async_setup_entity_state}
    await setup_entity[config[CONF_SCHEMA]](
        hass, config, async_add_entities, config_entry, discovery_data
    )
