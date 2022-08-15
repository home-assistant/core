"""Device automation helpers for toggle entity."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CONDITION,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
    CONF_STATE,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DEVICE_TRIGGER_BASE_SCHEMA, entity
from .const import (
    CONF_IS_OFF,
    CONF_IS_ON,
    CONF_TOGGLE,
    CONF_TURN_OFF,
    CONF_TURN_ON,
    CONF_TURNED_OFF,
    CONF_TURNED_ON,
)

# mypy: allow-untyped-calls, allow-untyped-defs

ENTITY_ACTIONS = [
    {
        # Turn entity off
        CONF_TYPE: CONF_TURN_OFF
    },
    {
        # Turn entity on
        CONF_TYPE: CONF_TURN_ON
    },
    {
        # Toggle entity
        CONF_TYPE: CONF_TOGGLE
    },
]

ENTITY_CONDITIONS = [
    {
        # True when entity is turned off
        CONF_CONDITION: "device",
        CONF_TYPE: CONF_IS_OFF,
    },
    {
        # True when entity is turned on
        CONF_CONDITION: "device",
        CONF_TYPE: CONF_IS_ON,
    },
]

ENTITY_TRIGGERS = [
    {
        # Trigger when entity is turned off
        CONF_PLATFORM: "device",
        CONF_TYPE: CONF_TURNED_OFF,
    },
    {
        # Trigger when entity is turned on
        CONF_PLATFORM: "device",
        CONF_TYPE: CONF_TURNED_ON,
    },
]

DEVICE_ACTION_TYPES = [CONF_TOGGLE, CONF_TURN_OFF, CONF_TURN_ON]

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(DEVICE_ACTION_TYPES),
    }
)

CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In([CONF_IS_OFF, CONF_IS_ON]),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)

_TOGGLE_TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In([CONF_TURNED_OFF, CONF_TURNED_ON]),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)

TRIGGER_SCHEMA = vol.Any(entity.TRIGGER_SCHEMA, _TOGGLE_TRIGGER_SCHEMA)


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
    domain: str,
) -> None:
    """Change state based on configuration."""
    action_type = config[CONF_TYPE]
    if action_type == CONF_TURN_ON:
        action = "turn_on"
    elif action_type == CONF_TURN_OFF:
        action = "turn_off"
    else:
        action = "toggle"

    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}

    await hass.services.async_call(
        domain, action, service_data, blocking=True, context=context
    )


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Evaluate state based on configuration."""
    if config[CONF_TYPE] == CONF_IS_ON:
        stat = "on"
    else:
        stat = "off"
    state_config = {
        CONF_CONDITION: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        CONF_STATE: stat,
    }
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]

    state_config = cv.STATE_CONDITION_SCHEMA(state_config)
    state_config = condition.state_validate_config(hass, state_config)
    return condition.state_from_config(state_config)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    if config[CONF_TYPE] not in [CONF_TURNED_ON, CONF_TURNED_OFF]:
        return await entity.async_attach_trigger(hass, config, action, trigger_info)

    if config[CONF_TYPE] == CONF_TURNED_ON:
        to_state = "on"
    else:
        to_state = "off"
    state_config = {
        CONF_PLATFORM: "state",
        state_trigger.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state_trigger.CONF_TO: to_state,
    }
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]

    state_config = await state_trigger.async_validate_trigger_config(hass, state_config)
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, trigger_info, platform_type="device"
    )


async def _async_get_automations(
    hass: HomeAssistant,
    device_id: str,
    automation_templates: list[dict[str, str]],
    domain: str,
) -> list[dict[str, str]]:
    """List device automations."""
    automations: list[dict[str, str]] = []
    entity_registry = er.async_get(hass)

    entries = [
        entry
        for entry in er.async_entries_for_device(entity_registry, device_id)
        if entry.domain == domain
    ]

    for entry in entries:
        automations.extend(
            {
                **template,
                "device_id": device_id,
                "entity_id": entry.entity_id,
                "domain": domain,
            }
            for template in automation_templates
        )

    return automations


async def async_get_actions(
    hass: HomeAssistant, device_id: str, domain: str
) -> list[dict[str, str]]:
    """List device actions."""
    return await _async_get_automations(hass, device_id, ENTITY_ACTIONS, domain)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str, domain: str
) -> list[dict[str, str]]:
    """List device conditions."""
    return await _async_get_automations(hass, device_id, ENTITY_CONDITIONS, domain)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str, domain: str
) -> list[dict[str, str]]:
    """List device triggers."""
    triggers = await entity.async_get_triggers(hass, device_id, domain)
    triggers.extend(
        await _async_get_automations(hass, device_id, ENTITY_TRIGGERS, domain)
    )
    return triggers


async def async_get_condition_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List condition capabilities."""
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    if config[CONF_TYPE] not in [CONF_TURNED_ON, CONF_TURNED_OFF]:
        return await entity.async_get_trigger_capabilities(hass, config)

    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }
