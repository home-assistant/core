"""Provides device automations for Climate."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import get_capability, get_supported_features
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN, const

ACTION_TYPES = {"set_hvac_mode", "set_preset_mode"}

SET_HVAC_MODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "set_hvac_mode",
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Required(const.ATTR_HVAC_MODE): vol.In(const.HVAC_MODES),
    }
)

SET_PRESET_MODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "set_preset_mode",
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Required(const.ATTR_PRESET_MODE): str,
    }
)

ACTION_SCHEMA = vol.Any(SET_HVAC_MODE_SCHEMA, SET_PRESET_MODE_SCHEMA)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for Climate devices."""
    registry = entity_registry.async_get(hass)
    actions = []

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

        actions.append({**base_action, CONF_TYPE: "set_hvac_mode"})
        if supported_features & const.SUPPORT_PRESET_MODE:
            actions.append({**base_action, CONF_TYPE: "set_preset_mode"})

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}

    if config[CONF_TYPE] == "set_hvac_mode":
        service = const.SERVICE_SET_HVAC_MODE
        service_data[const.ATTR_HVAC_MODE] = config[const.ATTR_HVAC_MODE]
    elif config[CONF_TYPE] == "set_preset_mode":
        service = const.SERVICE_SET_PRESET_MODE
        service_data[const.ATTR_PRESET_MODE] = config[const.ATTR_PRESET_MODE]

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    action_type = config[CONF_TYPE]

    fields = {}

    if action_type == "set_hvac_mode":
        try:
            hvac_modes = (
                get_capability(hass, config[ATTR_ENTITY_ID], const.ATTR_HVAC_MODES)
                or []
            )
        except HomeAssistantError:
            hvac_modes = []
        fields[vol.Required(const.ATTR_HVAC_MODE)] = vol.In(hvac_modes)
    elif action_type == "set_preset_mode":
        try:
            preset_modes = (
                get_capability(hass, config[ATTR_ENTITY_ID], const.ATTR_PRESET_MODES)
                or []
            )
        except HomeAssistantError:
            preset_modes = []
        fields[vol.Required(const.ATTR_PRESET_MODE)] = vol.In(preset_modes)

    return {"extra_fields": vol.Schema(fields)}
