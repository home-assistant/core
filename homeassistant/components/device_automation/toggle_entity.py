"""Device automation helpers for toggle entity."""
import voluptuous as vol

import homeassistant.components.automation.state as state
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
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers import condition, config_validation as cv, service

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

ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DOMAIN): str,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In([CONF_TOGGLE, CONF_TURN_OFF, CONF_TURN_ON]),
    }
)

CONDITION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONDITION): "device",
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DOMAIN): str,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In([CONF_IS_OFF, CONF_IS_ON]),
    }
)

TRIGGER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "device",
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DOMAIN): str,
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In([CONF_TURNED_OFF, CONF_TURNED_ON]),
    }
)


async def async_call_action_from_config(hass, config, variables, context, domain):
    """Change state based on configuration."""
    config = ACTION_SCHEMA(config)
    action_type = config[CONF_TYPE]
    if action_type == CONF_TURN_ON:
        action = "turn_on"
    elif action_type == CONF_TURN_OFF:
        action = "turn_off"
    else:
        action = "toggle"

    service_action = {
        service.CONF_SERVICE: "{}.{}".format(domain, action),
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
    }

    await service.async_call_from_config(
        hass, service_action, blocking=True, variables=variables, context=context
    )


def async_condition_from_config(config, config_validation):
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

    return condition.state_from_config(state_config, config_validation)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    trigger_type = config[CONF_TYPE]
    if trigger_type == CONF_TURNED_ON:
        from_state = "off"
        to_state = "on"
    else:
        from_state = "on"
        to_state = "off"
    state_config = {
        state.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state.CONF_FROM: from_state,
        state.CONF_TO: to_state,
    }

    return await state.async_attach_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )


async def _async_get_automations(hass, device_id, automation_templates, domain):
    """List device automations."""
    automations = []
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entries = [
        entry
        for entry in async_entries_for_device(entity_registry, device_id)
        if entry.domain == domain
    ]

    for entry in entries:
        automations.extend(
            (
                {
                    **template,
                    "device_id": device_id,
                    "entity_id": entry.entity_id,
                    "domain": domain,
                }
                for template in automation_templates
            )
        )

    return automations


async def async_get_actions(hass, device_id, domain):
    """List device actions."""
    print("YO")
    return await _async_get_automations(hass, device_id, ENTITY_ACTIONS, domain)


async def async_get_conditions(hass, device_id, domain):
    """List device conditions."""
    return await _async_get_automations(hass, device_id, ENTITY_CONDITIONS, domain)


async def async_get_triggers(hass, device_id, domain):
    """List device triggers."""
    return await _async_get_automations(hass, device_id, ENTITY_TRIGGERS, domain)
