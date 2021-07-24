"""Provides device actions for Select."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
)
from homeassistant.core import Context, HomeAssistant, HomeAssistantError
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import get_capability
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CYCLE,
    ATTR_OPTION,
    ATTR_OPTIONS,
    CONF_CYCLE,
    CONF_OPTION,
    DOMAIN,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
)

ACTION_TYPES = {SERVICE_SELECT_OPTION, SERVICE_SELECT_NEXT, SERVICE_SELECT_PREVIOUS}

SELECT_OPTION_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.Equal(SERVICE_SELECT_OPTION),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Required(CONF_OPTION): str,
    }
)

OFFSET_OPTION_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In({SERVICE_SELECT_NEXT, SERVICE_SELECT_PREVIOUS}),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Optional(CONF_CYCLE, default=True): bool,
    }
)

ACTION_SCHEMA = vol.Any(SELECT_OPTION_ACTION_SCHEMA, OFFSET_OPTION_ACTION_SCHEMA)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device actions for Select devices."""
    registry = await entity_registry.async_get_registry(hass)
    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
            CONF_TYPE: conf_type,
        }
        for conf_type in [
            SERVICE_SELECT_OPTION,
            SERVICE_SELECT_NEXT,
            SERVICE_SELECT_PREVIOUS,
        ]
        for entry in entity_registry.async_entries_for_device(registry, device_id)
        if entry.domain == DOMAIN
    ]


async def async_call_action_from_config(
    hass: HomeAssistant, config: ConfigType, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    action_type = config[CONF_TYPE]
    if action_type == SERVICE_SELECT_OPTION:
        await hass.services.async_call(
            DOMAIN,
            action_type,
            {
                ATTR_ENTITY_ID: config[CONF_ENTITY_ID],
                ATTR_OPTION: config[CONF_OPTION],
            },
            blocking=True,
            context=context,
        )
    else:
        await hass.services.async_call(
            DOMAIN,
            action_type,
            {
                ATTR_ENTITY_ID: config[CONF_ENTITY_ID],
                ATTR_CYCLE: config[CONF_CYCLE],
            },
            blocking=True,
            context=context,
        )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, Any]:
    """List action capabilities."""
    action_type = config[CONF_TYPE]

    if action_type == SERVICE_SELECT_OPTION:
        try:
            options = get_capability(hass, config[CONF_ENTITY_ID], ATTR_OPTIONS) or []
        except HomeAssistantError:
            options = []
        return {
            "extra_fields": vol.Schema({vol.Required(CONF_OPTION): vol.In(options)})
        }
    else:
        return {
            "extra_fields": vol.Schema({vol.Optional(CONF_CYCLE, default=True): bool})
        }
