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

from .const import ATTR_OPTION, ATTR_OPTIONS, CONF_OPTION, DOMAIN, SERVICE_SELECT_OPTION

ACTION_TYPES = {"select_option"}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Required(CONF_OPTION): str,
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device actions for Select devices."""
    registry = await entity_registry.async_get_registry(hass)
    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
            CONF_TYPE: "select_option",
        }
        for entry in entity_registry.async_entries_for_device(registry, device_id)
        if entry.domain == DOMAIN
    ]


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: config[CONF_ENTITY_ID],
            ATTR_OPTION: config[CONF_OPTION],
        },
        blocking=True,
        context=context,
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, Any]:
    """List action capabilities."""
    try:
        options = get_capability(hass, config[CONF_ENTITY_ID], ATTR_OPTIONS) or []
    except HomeAssistantError:
        options = []

    return {"extra_fields": vol.Schema({vol.Required(CONF_OPTION): vol.In(options)})}
