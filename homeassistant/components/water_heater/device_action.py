"""Provides device automations for Water Heater."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

ACTION_TYPES = {"turn_on", "turn_off"}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for Water Heater devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = []

    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        base_action = {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        actions.append({**base_action, CONF_TYPE: "turn_on"})
        actions.append({**base_action, CONF_TYPE: "turn_off"})

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}

    if config[CONF_TYPE] == "turn_on":
        service = SERVICE_TURN_ON
    elif config[CONF_TYPE] == "turn_off":
        service = SERVICE_TURN_OFF

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )
