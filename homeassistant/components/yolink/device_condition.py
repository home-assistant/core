"""Provide the device conditions for YoLink."""
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
from homeassistant.helpers import condition, config_validation as cv, entity_registry
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN

# TODO specify your supported condition types.
CONDITION_TYPES = {
    "is_on",
    "is_off",
    "is_open",
    "is_closed",
    "water_leak",
    "motion_detected",
}

CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for YoLink devices."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)
    registry = await entity_registry.async_get_registry(hass)
    conditions = []

    base_condition = {
        CONF_CONDITION: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }
    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.platform != DOMAIN:
            continue

        if device.model in ["DoorSensor"]:
            if entry.device_class == "door":
                conditions.append(
                    {
                        **base_condition,
                        CONF_TYPE: "is_open",
                        CONF_ENTITY_ID: entry.entity_id,
                    }
                )
                conditions.append(
                    {
                        **base_condition,
                        CONF_TYPE: "is_closed",
                        CONF_ENTITY_ID: entry.entity_id,
                    }
                )
        elif device.model in ["Outlet", "Siren"]:
            conditions.append(
                {
                    **base_condition,
                    CONF_TYPE: "is_on",
                    CONF_ENTITY_ID: entry.entity_id,
                }
            )
            conditions.append(
                {
                    **base_condition,
                    CONF_TYPE: "is_off",
                    CONF_ENTITY_ID: entry.entity_id,
                }
            )
            break
        elif device.model in ["MotionSensor"]:
            if entry.device_class == "motion":
                conditions.append(
                    {
                        **base_condition,
                        CONF_TYPE: "motion_detected",
                        CONF_ENTITY_ID: entry.entity_id,
                    }
                )
        elif device.model in ["LeakSensor"]:
            if entry.device_class == "moisture":
                conditions.append(
                    {
                        **base_condition,
                        CONF_TYPE: "water_leak",
                        CONF_ENTITY_ID: entry.entity_id,
                    }
                )

    return conditions


@callback
def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config_validation:
        config = CONDITION_SCHEMA(config)
    if config[CONF_TYPE] == "is_on":
        state = STATE_ON
    else:
        state = STATE_OFF

    @callback
    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        return condition.state(hass, config[ATTR_ENTITY_ID], state)

    return test_is_state
