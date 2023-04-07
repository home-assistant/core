"""Provide the device automations for Alarm control panel."""
from __future__ import annotations

from typing import Final

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.entity import get_supported_features
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN
from .const import (
    CONDITION_ARMED_AWAY,
    CONDITION_ARMED_CUSTOM_BYPASS,
    CONDITION_ARMED_HOME,
    CONDITION_ARMED_NIGHT,
    CONDITION_ARMED_VACATION,
    CONDITION_DISARMED,
    CONDITION_TRIGGERED,
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_ARM_VACATION,
)

CONDITION_TYPES: Final[set[str]] = {
    CONDITION_TRIGGERED,
    CONDITION_DISARMED,
    CONDITION_ARMED_HOME,
    CONDITION_ARMED_AWAY,
    CONDITION_ARMED_NIGHT,
    CONDITION_ARMED_VACATION,
    CONDITION_ARMED_CUSTOM_BYPASS,
}

CONDITION_SCHEMA: Final = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Alarm control panel devices."""
    registry = er.async_get(hass)
    conditions = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        supported_features = get_supported_features(hass, entry.entity_id)

        # Add conditions for each entity that belongs to this integration
        base_condition = {
            CONF_CONDITION: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        conditions += [
            {**base_condition, CONF_TYPE: CONDITION_DISARMED},
            {**base_condition, CONF_TYPE: CONDITION_TRIGGERED},
        ]
        if supported_features & SUPPORT_ALARM_ARM_HOME:
            conditions.append({**base_condition, CONF_TYPE: CONDITION_ARMED_HOME})
        if supported_features & SUPPORT_ALARM_ARM_AWAY:
            conditions.append({**base_condition, CONF_TYPE: CONDITION_ARMED_AWAY})
        if supported_features & SUPPORT_ALARM_ARM_NIGHT:
            conditions.append({**base_condition, CONF_TYPE: CONDITION_ARMED_NIGHT})
        if supported_features & SUPPORT_ALARM_ARM_VACATION:
            conditions.append({**base_condition, CONF_TYPE: CONDITION_ARMED_VACATION})
        if supported_features & SUPPORT_ALARM_ARM_CUSTOM_BYPASS:
            conditions.append(
                {**base_condition, CONF_TYPE: CONDITION_ARMED_CUSTOM_BYPASS}
            )

    return conditions


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config[CONF_TYPE] == CONDITION_TRIGGERED:
        state = STATE_ALARM_TRIGGERED
    elif config[CONF_TYPE] == CONDITION_DISARMED:
        state = STATE_ALARM_DISARMED
    elif config[CONF_TYPE] == CONDITION_ARMED_HOME:
        state = STATE_ALARM_ARMED_HOME
    elif config[CONF_TYPE] == CONDITION_ARMED_AWAY:
        state = STATE_ALARM_ARMED_AWAY
    elif config[CONF_TYPE] == CONDITION_ARMED_NIGHT:
        state = STATE_ALARM_ARMED_NIGHT
    elif config[CONF_TYPE] == CONDITION_ARMED_VACATION:
        state = STATE_ALARM_ARMED_VACATION
    elif config[CONF_TYPE] == CONDITION_ARMED_CUSTOM_BYPASS:
        state = STATE_ALARM_ARMED_CUSTOM_BYPASS

    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        return condition.state(hass, config[ATTR_ENTITY_ID], state)

    return test_is_state
