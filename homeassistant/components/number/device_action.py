"""Provides device actions for Number."""
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
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from . import DOMAIN, const

ATYP_SET_VALUE = "set_value"

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): ATYP_SET_VALUE,
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Required(const.ATTR_VALUE): vol.Coerce(float),
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device actions for Number."""
    registry = await entity_registry.async_get_registry(hass)
    actions: list[dict[str, Any]] = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: ATYP_SET_VALUE,
            }
        )

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    await hass.services.async_call(
        DOMAIN,
        const.SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: config[CONF_ENTITY_ID],
            const.ATTR_VALUE: config[const.ATTR_VALUE],
        },
        blocking=True,
        context=context,
    )


async def async_get_action_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List action capabilities."""
    fields = {vol.Required(const.ATTR_VALUE): vol.Coerce(float)}

    return {"extra_fields": vol.Schema(fields)}
