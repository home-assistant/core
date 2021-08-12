"""Provides device actions for Humidifier."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
)
from homeassistant.core import Context, HomeAssistant, HomeAssistantError
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import get_capability, get_supported_features

from . import DOMAIN, const

SET_HUMIDITY_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "set_humidity",
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Required(const.ATTR_HUMIDITY): vol.Coerce(int),
    }
)

SET_MODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "set_mode",
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Required(ATTR_MODE): cv.string,
    }
)

ONOFF_SCHEMA = toggle_entity.ACTION_SCHEMA.extend({vol.Required(CONF_DOMAIN): DOMAIN})

ACTION_SCHEMA = vol.Any(SET_HUMIDITY_SCHEMA, SET_MODE_SCHEMA, ONOFF_SCHEMA)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device actions for Humidifier devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = await toggle_entity.async_get_actions(hass, device_id, DOMAIN)

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        supported_features = get_supported_features(hass, entry.entity_id)

        base_action = {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }
        actions.append({**base_action, CONF_TYPE: "set_humidity"})

        if supported_features & const.SUPPORT_MODES:
            actions.append({**base_action, CONF_TYPE: "set_mode"})

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}

    if config[CONF_TYPE] == "set_humidity":
        service = const.SERVICE_SET_HUMIDITY
        service_data[const.ATTR_HUMIDITY] = config[const.ATTR_HUMIDITY]
    elif config[CONF_TYPE] == "set_mode":
        service = const.SERVICE_SET_MODE
        service_data[ATTR_MODE] = config[ATTR_MODE]
    else:
        return await toggle_entity.async_call_action_from_config(
            hass, config, variables, context, DOMAIN
        )

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )


async def async_get_action_capabilities(hass, config):
    """List action capabilities."""
    action_type = config[CONF_TYPE]

    fields = {}

    if action_type == "set_humidity":
        fields[vol.Required(const.ATTR_HUMIDITY)] = vol.Coerce(int)
    elif action_type == "set_mode":
        try:
            available_modes = (
                get_capability(hass, config[ATTR_ENTITY_ID], const.ATTR_AVAILABLE_MODES)
                or []
            )
        except HomeAssistantError:
            available_modes = []
        fields[vol.Required(ATTR_MODE)] = vol.In(available_modes)
    else:
        return {}

    return {"extra_fields": vol.Schema(fields)}
