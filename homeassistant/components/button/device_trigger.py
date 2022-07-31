"""Provides device triggers for Button."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.automation import (
    AutomationActionType,
    AutomationTriggerInfo,
)
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers.state import (
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
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

TRIGGER_TYPES = {"pressed"}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for button devices."""
    registry = entity_registry.async_get(hass)
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
            CONF_TYPE: "pressed",
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

    state_config = await async_validate_state_trigger_config(hass, state_config)
    return await async_attach_state_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )
