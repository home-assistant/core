"""Provides device automations for Vacuum."""
from typing import Any, Dict, List
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CONDITION,
    CONF_DOMAIN,
    CONF_TYPE,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
)

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    STATE_ERROR,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers import condition, config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType, TemplateVarsType
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from . import DOMAIN

CONDITION_TYPES = {
    "is_cleaning",
    "is_docked",
    "is_paused",
    "is_idle",
    "is_returning",
    "is_error",
}

CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> List[Dict[str, str]]:
    """List device conditions for Vacuum devices."""
    registry = await entity_registry.async_get_registry(hass)
    conditions: List[Dict[str, Any]] = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        # Add conditions for each entity that belongs to this integration
        conditions.append(
            {
                CONF_CONDITION: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "is_cleaning",
            }
        )
        conditions.append(
            {
                CONF_CONDITION: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "is_docked",
            }
        )
        conditions.append(
            {
                CONF_CONDITION: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "is_paused",
            }
        )
        conditions.append(
            {
                CONF_CONDITION: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "is_idle",
            }
        )
        conditions.append(
            {
                CONF_CONDITION: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "is_returning",
            }
        )
        conditions.append(
            {
                CONF_CONDITION: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "is_error",
            }
        )

    return conditions


def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config_validation:
        config = CONDITION_SCHEMA(config)
    if config[CONF_TYPE] == "is_cleaning":
        state = STATE_CLEANING
    elif config[CONF_TYPE] == "is_docked":
        state = STATE_DOCKED
    elif config[CONF_TYPE] == "is_paused":
        state = STATE_PAUSED
    elif config[CONF_TYPE] == "is_idle":
        state = STATE_IDLE
    elif config[CONF_TYPE] == "is_returning":
        state = STATE_RETURNING
    elif config[CONF_TYPE] == "is_error":
        state = STATE_ERROR

    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        return condition.state(hass, config[ATTR_ENTITY_ID], state)

    return test_is_state
