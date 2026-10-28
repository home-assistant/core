"""Provides device automations for Climate."""

import probatio

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import (
    numeric_state as numeric_state_trigger,
    state as state_trigger,
)
from homeassistant.components.homeassistant.triggers.numeric_state import (
    NumericStateTriggerArgument,
)
from homeassistant.components.homeassistant.triggers.state import StateTriggerArgument
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
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, HVAC_MODES, ClimateEntityStateAttribute

TRIGGER_TYPES = {
    "current_temperature_changed",
    "current_humidity_changed",
    "hvac_mode_changed",
}

HVAC_MODE_TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        probatio.Required(CONF_TYPE): "hvac_mode_changed",
        probatio.Required(StateTriggerArgument.TO): probatio.In(HVAC_MODES),
        probatio.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)

CURRENT_TRIGGER_SCHEMA = probatio.All(
    DEVICE_TRIGGER_BASE_SCHEMA.extend(
        {
            probatio.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
            probatio.Required(CONF_TYPE): probatio.In(
                ["current_temperature_changed", "current_humidity_changed"]
            ),
            probatio.Optional(CONF_BELOW): probatio.Any(probatio.Coerce(float)),
            probatio.Optional(CONF_ABOVE): probatio.Any(probatio.Coerce(float)),
            probatio.Optional(CONF_FOR): cv.positive_time_period_dict,
        }
    ),
    probatio.AtLeastOne(CONF_BELOW, CONF_ABOVE),
)

TRIGGER_SCHEMA = probatio.TaggedUnion(
    CONF_TYPE,
    {
        "hvac_mode_changed": HVAC_MODE_TRIGGER_SCHEMA,
        "current_temperature_changed": CURRENT_TRIGGER_SCHEMA,
        "current_humidity_changed": CURRENT_TRIGGER_SCHEMA,
    },
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for Climate devices."""
    registry = er.async_get(hass)
    triggers = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        state = hass.states.get(entry.entity_id)

        # Add triggers for each entity that belongs to this integration
        base_trigger = {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.id,
        }

        triggers.append(
            {
                **base_trigger,
                CONF_TYPE: "hvac_mode_changed",
            }
        )

        if (
            state
            and ClimateEntityStateAttribute.CURRENT_TEMPERATURE in state.attributes
        ):
            triggers.append(
                {
                    **base_trigger,
                    CONF_TYPE: "current_temperature_changed",
                }
            )

        if state and ClimateEntityStateAttribute.CURRENT_HUMIDITY in state.attributes:
            triggers.append(
                {
                    **base_trigger,
                    CONF_TYPE: "current_humidity_changed",
                }
            )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    if (trigger_type := config[CONF_TYPE]) == "hvac_mode_changed":
        state_config: ConfigType = {
            StateTriggerArgument.PLATFORM: "state",
            StateTriggerArgument.ENTITY_ID: config[CONF_ENTITY_ID],
            StateTriggerArgument.TO: config[StateTriggerArgument.TO],
            StateTriggerArgument.FROM: [
                mode for mode in HVAC_MODES if mode != config[StateTriggerArgument.TO]
            ],
        }
        if CONF_FOR in config:
            state_config[StateTriggerArgument.FOR] = config[CONF_FOR]
        state_config = await state_trigger.async_validate_trigger_config(
            hass, state_config
        )
        return await state_trigger.async_attach_trigger(
            hass, state_config, action, trigger_info, platform_type="device"
        )

    numeric_state_config: ConfigType = {
        NumericStateTriggerArgument.PLATFORM: "numeric_state",
        NumericStateTriggerArgument.ENTITY_ID: config[CONF_ENTITY_ID],
    }

    if trigger_type == "current_temperature_changed":
        numeric_state_config[NumericStateTriggerArgument.VALUE_TEMPLATE] = (
            "{{ state.attributes.current_temperature }}"
        )
    else:  # trigger_type == "current_humidity_changed"
        numeric_state_config[NumericStateTriggerArgument.VALUE_TEMPLATE] = (
            "{{ state.attributes.current_humidity }}"
        )

    if CONF_ABOVE in config:
        numeric_state_config[NumericStateTriggerArgument.ABOVE] = config[CONF_ABOVE]
    if CONF_BELOW in config:
        numeric_state_config[NumericStateTriggerArgument.BELOW] = config[CONF_BELOW]
    if CONF_FOR in config:
        numeric_state_config[NumericStateTriggerArgument.FOR] = config[CONF_FOR]

    numeric_state_config = await numeric_state_trigger.async_validate_trigger_config(
        hass, numeric_state_config
    )
    return await numeric_state_trigger.async_attach_trigger(
        hass, numeric_state_config, action, trigger_info, platform_type="device"
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, probatio.Schema]:
    """List trigger capabilities."""
    trigger_type = config[CONF_TYPE]

    if trigger_type == "hvac_action_changed":
        return {}

    if trigger_type == "hvac_mode_changed":
        return {
            "extra_fields": probatio.Schema(
                {
                    probatio.Required(StateTriggerArgument.TO): probatio.In(HVAC_MODES),
                    probatio.Optional(CONF_FOR): cv.positive_time_period_dict,
                }
            )
        }

    if trigger_type == "current_temperature_changed":
        unit_of_measurement: str = hass.config.units.temperature_unit
    else:
        unit_of_measurement = PERCENTAGE

    return {
        "extra_fields": probatio.Schema(
            {
                probatio.Optional(
                    CONF_ABOVE, description={"suffix": unit_of_measurement}
                ): probatio.Coerce(float),
                probatio.Optional(
                    CONF_BELOW, description={"suffix": unit_of_measurement}
                ): probatio.Coerce(float),
                probatio.Optional(CONF_FOR): cv.positive_time_period_dict,
            }
        )
    }
