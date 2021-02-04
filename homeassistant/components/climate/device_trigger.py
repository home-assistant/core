"""Provides device automations for Climate."""
from typing import List

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import (
    numeric_state as numeric_state_trigger,
    state as state_trigger,
)
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
    CONF_TYPE,
    PERCENTAGE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN, const

TRIGGER_TYPES = {
    "current_temperature_changed",
    "current_humidity_changed",
    "hvac_mode_changed",
}

HVAC_MODE_TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): "hvac_mode_changed",
        vol.Required(state_trigger.CONF_TO): vol.In(const.HVAC_MODES),
    }
)

CURRENT_TRIGGER_SCHEMA = vol.All(
    TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_TYPE): vol.In(
                ["current_temperature_changed", "current_humidity_changed"]
            ),
            vol.Optional(CONF_BELOW): vol.Any(vol.Coerce(float)),
            vol.Optional(CONF_ABOVE): vol.Any(vol.Coerce(float)),
            vol.Optional(CONF_FOR): cv.positive_time_period_dict,
        }
    ),
    cv.has_at_least_one_key(CONF_BELOW, CONF_ABOVE),
)

TRIGGER_SCHEMA = vol.Any(HVAC_MODE_TRIGGER_SCHEMA, CURRENT_TRIGGER_SCHEMA)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for Climate devices."""
    registry = await entity_registry.async_get_registry(hass)
    triggers = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        state = hass.states.get(entry.entity_id)

        # Add triggers for each entity that belongs to this integration
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "hvac_mode_changed",
            }
        )

        if state and const.ATTR_CURRENT_TEMPERATURE in state.attributes:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "current_temperature_changed",
                }
            )

        if state and const.ATTR_CURRENT_HUMIDITY in state.attributes:
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "current_humidity_changed",
                }
            )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    config = TRIGGER_SCHEMA(config)
    trigger_type = config[CONF_TYPE]

    if trigger_type == "hvac_mode_changed":
        state_config = {
            state_trigger.CONF_PLATFORM: "state",
            state_trigger.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
            state_trigger.CONF_TO: config[state_trigger.CONF_TO],
            state_trigger.CONF_FROM: [
                mode
                for mode in const.HVAC_MODES
                if mode != config[state_trigger.CONF_TO]
            ],
        }
        if CONF_FOR in config:
            state_config[CONF_FOR] = config[CONF_FOR]
        state_config = state_trigger.TRIGGER_SCHEMA(state_config)
        return await state_trigger.async_attach_trigger(
            hass, state_config, action, automation_info, platform_type="device"
        )

    numeric_state_config = {
        numeric_state_trigger.CONF_PLATFORM: "numeric_state",
        numeric_state_trigger.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
    }

    if trigger_type == "current_temperature_changed":
        numeric_state_config[
            numeric_state_trigger.CONF_VALUE_TEMPLATE
        ] = "{{ state.attributes.current_temperature }}"
    else:
        numeric_state_config[
            numeric_state_trigger.CONF_VALUE_TEMPLATE
        ] = "{{ state.attributes.current_humidity }}"

    if CONF_ABOVE in config:
        numeric_state_config[CONF_ABOVE] = config[CONF_ABOVE]
    if CONF_BELOW in config:
        numeric_state_config[CONF_BELOW] = config[CONF_BELOW]
    if CONF_FOR in config:
        numeric_state_config[CONF_FOR] = config[CONF_FOR]

    numeric_state_config = numeric_state_trigger.TRIGGER_SCHEMA(numeric_state_config)
    return await numeric_state_trigger.async_attach_trigger(
        hass, numeric_state_config, action, automation_info, platform_type="device"
    )


async def async_get_trigger_capabilities(hass: HomeAssistant, config):
    """List trigger capabilities."""
    trigger_type = config[CONF_TYPE]

    if trigger_type == "hvac_action_changed":
        return None

    if trigger_type == "hvac_mode_changed":
        return {
            "extra_fields": vol.Schema(
                {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
            )
        }

    if trigger_type == "current_temperature_changed":
        unit_of_measurement = hass.config.units.temperature_unit
    else:
        unit_of_measurement = PERCENTAGE

    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional(
                    CONF_ABOVE, description={"suffix": unit_of_measurement}
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_BELOW, description={"suffix": unit_of_measurement}
                ): vol.Coerce(float),
                vol.Optional(CONF_FOR): cv.positive_time_period_dict,
            }
        )
    }
