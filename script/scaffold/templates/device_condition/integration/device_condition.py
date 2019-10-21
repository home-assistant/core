"""Provides device automations for NEW_NAME."""
from typing import List
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DOMAIN,
    CONF_TYPE,
    CONF_PLATFORM,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import condition, entity_registry
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from . import DOMAIN

# TODO specify your supported condition types.
CONDITION_TYPES = {"is_on"}

CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES)}
)


async def async_get_conditions(hass: HomeAssistant, device_id: str) -> List[str]:
    """List device conditions for NEW_NAME devices."""
    registry = await entity_registry.async_get_registry(hass)
    conditions = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        # Add conditions for each entity that belongs to this integration
        # TODO add your own conditions.
        conditions.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "is_on",
            }
        )

    return conditions


def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config_validation:
        config = CONDITION_SCHEMA(config)

    def test_is_on(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is on."""
        return condition.state(hass, config[ATTR_ENTITY_ID], STATE_ON)

    return test_is_on
