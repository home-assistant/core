"""Provides device automations for Alarm control panel."""
from typing import List, Optional

import voluptuous as vol

from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    CONF_CODE,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from . import ATTR_CODE_ARM_REQUIRED, DOMAIN
from .const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_TRIGGER,
)

ACTION_TYPES = {"arm_away", "arm_home", "arm_night", "disarm", "trigger"}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Optional(CONF_CODE): cv.string,
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions for Alarm control panel devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        state = hass.states.get(entry.entity_id)

        # We need a state or else we can't populate the HVAC and preset modes.
        if state is None:
            continue

        supported_features = state.attributes["supported_features"]

        # Add actions for each entity that belongs to this integration
        if supported_features & SUPPORT_ALARM_ARM_AWAY:
            actions.append(
                {
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "arm_away",
                }
            )
        if supported_features & SUPPORT_ALARM_ARM_HOME:
            actions.append(
                {
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "arm_home",
                }
            )
        if supported_features & SUPPORT_ALARM_ARM_NIGHT:
            actions.append(
                {
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "arm_night",
                }
            )
        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.entity_id,
                CONF_TYPE: "disarm",
            }
        )
        if supported_features & SUPPORT_ALARM_TRIGGER:
            actions.append(
                {
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "trigger",
                }
            )

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Optional[Context]
) -> None:
    """Execute a device action."""
    config = ACTION_SCHEMA(config)

    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}
    if CONF_CODE in config:
        service_data[ATTR_CODE] = config[CONF_CODE]

    if config[CONF_TYPE] == "arm_away":
        service = SERVICE_ALARM_ARM_AWAY
    elif config[CONF_TYPE] == "arm_home":
        service = SERVICE_ALARM_ARM_HOME
    elif config[CONF_TYPE] == "arm_night":
        service = SERVICE_ALARM_ARM_NIGHT
    elif config[CONF_TYPE] == "disarm":
        service = SERVICE_ALARM_DISARM
    elif config[CONF_TYPE] == "trigger":
        service = SERVICE_ALARM_TRIGGER

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )


async def async_get_action_capabilities(hass, config):
    """List action capabilities."""
    state = hass.states.get(config[CONF_ENTITY_ID])
    code_required = state.attributes.get(ATTR_CODE_ARM_REQUIRED) if state else False

    if config[CONF_TYPE] == "trigger" or (
        config[CONF_TYPE] != "disarm" and not code_required
    ):
        return {}

    return {"extra_fields": vol.Schema({vol.Optional(CONF_CODE): str})}
