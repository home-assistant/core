"""Device automation helpers for toggle entity."""
from typing import Any, Dict, List

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    state as state_automation,
)
from homeassistant.components.device_automation.const import (
    CONF_IS_OFF,
    CONF_IS_ON,
    CONF_TOGGLE,
    CONF_TURN_OFF,
    CONF_TURN_ON,
    CONF_TURNED_OFF,
    CONF_TURNED_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CONDITION,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import TRIGGER_BASE_SCHEMA

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

TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In([CONF_TURNED_OFF, CONF_TURNED_ON]),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context,
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
def async_condition_from_config(config: ConfigType) -> condition.ConditionCheckerType:
    """Evaluate state based on configuration."""
    condition_type = config[CONF_TYPE]
    if condition_type == CONF_IS_ON:
        stat = "on"
    else:
        stat = "off"
    state_config = {
        condition.CONF_CONDITION: "state",
        condition.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        condition.CONF_STATE: stat,
    }
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]

    return condition.state_from_config(state_config)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    trigger_type = config[CONF_TYPE]
    if trigger_type == CONF_TURNED_ON:
        from_state = "off"
        to_state = "on"
    else:
        from_state = "on"
        to_state = "off"
    state_config = {
        state_automation.CONF_PLATFORM: "state",
        state_automation.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state_automation.CONF_FROM: from_state,
        state_automation.CONF_TO: to_state,
    }
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]

    state_config = state_automation.TRIGGER_SCHEMA(state_config)
    return await state_automation.async_attach_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )


async def _async_get_automations(
    hass: HomeAssistant, device_id: str, automation_templates: List[dict], domain: str
) -> List[dict]:
    """List device automations."""
    automations: List[Dict[str, Any]] = []
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entries = [
        entry
        for entry in async_entries_for_device(entity_registry, device_id)
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
) -> List[dict]:
    """List device actions."""
    return await _async_get_automations(hass, device_id, ENTITY_ACTIONS, domain)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str, domain: str
) -> List[Dict[str, str]]:
    """List device conditions."""
    return await _async_get_automations(hass, device_id, ENTITY_CONDITIONS, domain)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str, domain: str
) -> List[dict]:
    """List device triggers."""
    return await _async_get_automations(hass, device_id, ENTITY_TRIGGERS, domain)


async def async_get_condition_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List condition capabilities."""
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }


async def async_get_trigger_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List trigger capabilities."""
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }
