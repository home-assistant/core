"""Device automation helpers for entity."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import CONF_ENTITY_ID, CONF_FOR, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import DEVICE_TRIGGER_BASE_SCHEMA
from .const import CONF_CHANGED_STATES

# mypy: allow-untyped-calls, allow-untyped-defs

ENTITY_TRIGGERS = [
    {
        # Trigger when entity is turned on or off
        CONF_PLATFORM: "device",
        CONF_TYPE: CONF_CHANGED_STATES,
    },
]

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In([CONF_CHANGED_STATES]),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    to_state = None
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


async def async_get_triggers(
    hass: HomeAssistant, device_id: str, domain: str
) -> list[dict[str, str]]:
    """List device triggers."""
    return await _async_get_automations(hass, device_id, ENTITY_TRIGGERS, domain)


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }
