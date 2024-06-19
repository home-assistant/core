"""Provide the device conditions for NEW_NAME."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN

# TODO specify your supported condition types.
CONDITION_TYPES = {"is_on", "is_off"}

CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for NEW_NAME devices."""
    registry = er.async_get(hass)
    conditions = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        # Add conditions for each entity that belongs to this integration
        # TODO add your own conditions.
        base_condition = {
            CONF_CONDITION: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        conditions += [{**base_condition, CONF_TYPE: cond} for cond in CONDITION_TYPES]

    return conditions


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config[CONF_TYPE] == "is_on":
        state = STATE_ON
    else:
        state = STATE_OFF

    @callback
    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        return condition.state(hass, config[ATTR_ENTITY_ID], state)

    return test_is_state
