"""Provides device triggers for Select."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers.state import (
    CONF_FOR,
    CONF_FROM,
    CONF_TO,
    async_attach_trigger as async_attach_state_trigger,
    async_validate_trigger_config as async_validate_state_trigger_config,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity import get_capability
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_OPTIONS, DOMAIN

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
) -> list[dict[str, str]]:
    """List device triggers for Select devices."""
    registry = er.async_get(hass)
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
            CONF_TYPE: "current_option_changed",
        }
        for entry in er.async_entries_for_device(registry, device_id)
        if entry.domain == DOMAIN
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
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

    state_config = await async_validate_state_trigger_config(hass, state_config)
    return await async_attach_state_trigger(
        hass, state_config, action, trigger_info, platform_type="device"
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
