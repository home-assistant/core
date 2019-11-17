"""Provides device automations for Humidifier."""
from typing import Optional, List
import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DOMAIN,
    CONF_TYPE,
    CONF_DEVICE_ID,
    CONF_ENTITY_ID,
)
from homeassistant.core import HomeAssistant, Context
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv
from . import DOMAIN, const

ACTION_TYPES = {"set_humidifier_mode", "set_preset_mode"}

SET_HUMIDIFIER_MODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "set_humidifier_mode",
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Required(const.ATTR_HUMIDIFIER_MODE): vol.In(const.HUMIDIFIER_MODES),
    }
)

SET_PRESET_MODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "set_preset_mode",
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Required(const.ATTR_PRESET_MODE): str,
    }
)

ACTION_SCHEMA = vol.Any(SET_HUMIDIFIER_MODE_SCHEMA, SET_PRESET_MODE_SCHEMA)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions for Humidifier devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        state = hass.states.get(entry.entity_id)

        # We need a state or else we can't populate the HUMIDIFIER and preset modes.
        if state is None:
            continue

        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "set_humidifier_mode",
            }
        )
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "set_preset_mode",
            }
        )

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Optional[Context]
) -> None:
    """Execute a device action."""
    config = ACTION_SCHEMA(config)

    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}

    if config[CONF_TYPE] == "set_humidifier_mode":
        service = const.SERVICE_SET_HUMIDIFIER_MODE
        service_data[const.ATTR_HUMIDIFIER_MODE] = config[const.ATTR_HUMIDIFIER_MODE]
    elif config[CONF_TYPE] == "set_preset_mode":
        service = const.SERVICE_SET_PRESET_MODE
        service_data[const.ATTR_PRESET_MODE] = config[const.ATTR_PRESET_MODE]

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )


async def async_get_action_capabilities(hass, config):
    """List action capabilities."""
    state = hass.states.get(config[CONF_ENTITY_ID])
    action_type = config[CONF_TYPE]

    fields = {}

    if action_type == "set_humidifier_mode":
        humidifier_modes = (
            state.attributes[const.ATTR_HUMIDIFIER_MODES] if state else []
        )
        fields[vol.Required(const.ATTR_HUMIDIFIER_MODE)] = vol.In(humidifier_modes)
    elif action_type == "set_preset_mode":
        if state:
            preset_modes = state.attributes.get(const.ATTR_PRESET_MODES, [])
        else:
            preset_modes = []
        fields[vol.Required(const.ATTR_PRESET_MODE)] = vol.In(preset_modes)

    return {"extra_fields": vol.Schema(fields)}
