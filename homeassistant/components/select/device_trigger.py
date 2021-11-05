"""Provides device triggers for Select."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers.state import (
    CONF_FOR,
    CONF_FROM,
    CONF_TO,
    TRIGGER_SCHEMA as STATE_TRIGGER_SCHEMA,
    async_attach_trigger as async_attach_state_trigger,
)
from homeassistant.components.select.const import ATTR_OPTIONS
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.entity import get_capability
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

TRIGGER_TYPES = {"current_option_changed"}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
        vol.Optional(CONF_TO): vol.Any(vol.Coerce(str)),
        vol.Optional(CONF_FROM): vol.Any(vol.Coerce(str)),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for Select devices."""
    registry = await entity_registry.async_get_registry(hass)
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
            CONF_TYPE: "current_option_changed",
        }
        for entry in entity_registry.async_entries_for_device(registry, device_id)
        if entry.domain == DOMAIN
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: AutomationTriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    state_config = {
        CONF_PLATFORM: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
    }

    if CONF_TO in config:
        state_config[CONF_TO] = config[CONF_TO]

    if CONF_FROM in config:
        state_config[CONF_FROM] = config[CONF_FROM]

    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]

    state_config = STATE_TRIGGER_SCHEMA(state_config)
    return await async_attach_state_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""
    try:
        options = get_capability(hass, config[CONF_ENTITY_ID], ATTR_OPTIONS) or []
    except HomeAssistantError:
        options = []

    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional(CONF_FROM): vol.In(options),
                vol.Optional(CONF_TO): vol.In(options),
                vol.Optional(CONF_FOR): cv.positive_time_period_dict,
            }
        )
    }
