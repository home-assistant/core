"""Provides device automations for Alarm control panel."""
from __future__ import annotations

from typing import Final

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
    SERVICE_ALARM_ARM_VACATION,
    SERVICE_ALARM_DISARM,
    SERVICE_ALARM_TRIGGER,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import get_supported_features
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import ATTR_CODE_ARM_REQUIRED, DOMAIN
from .const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
    SUPPORT_ALARM_ARM_VACATION,
    SUPPORT_ALARM_TRIGGER,
)

ACTION_TYPES: Final[set[str]] = {
    "arm_away",
    "arm_home",
    "arm_night",
    "arm_vacation",
    "disarm",
    "trigger",
}

ACTION_SCHEMA: Final = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Optional(CONF_CODE): cv.string,
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for Alarm control panel devices."""
    registry = er.async_get(hass)
    actions = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        supported_features = get_supported_features(hass, entry.entity_id)

        base_action: dict = {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        # Add actions for each entity that belongs to this integration
        if supported_features & SUPPORT_ALARM_ARM_AWAY:
            actions.append({**base_action, CONF_TYPE: "arm_away"})
        if supported_features & SUPPORT_ALARM_ARM_HOME:
            actions.append({**base_action, CONF_TYPE: "arm_home"})
        if supported_features & SUPPORT_ALARM_ARM_NIGHT:
            actions.append({**base_action, CONF_TYPE: "arm_night"})
        if supported_features & SUPPORT_ALARM_ARM_VACATION:
            actions.append({**base_action, CONF_TYPE: "arm_vacation"})
        actions.append({**base_action, CONF_TYPE: "disarm"})
        if supported_features & SUPPORT_ALARM_TRIGGER:
            actions.append({**base_action, CONF_TYPE: "trigger"})

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}
    if CONF_CODE in config:
        service_data[ATTR_CODE] = config[CONF_CODE]

    if config[CONF_TYPE] == "arm_away":
        service = SERVICE_ALARM_ARM_AWAY
    elif config[CONF_TYPE] == "arm_home":
        service = SERVICE_ALARM_ARM_HOME
    elif config[CONF_TYPE] == "arm_night":
        service = SERVICE_ALARM_ARM_NIGHT
    elif config[CONF_TYPE] == "arm_vacation":
        service = SERVICE_ALARM_ARM_VACATION
    elif config[CONF_TYPE] == "disarm":
        service = SERVICE_ALARM_DISARM
    elif config[CONF_TYPE] == "trigger":
        service = SERVICE_ALARM_TRIGGER

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    # We need to refer to the state directly because ATTR_CODE_ARM_REQUIRED is not a
    # capability attribute
    state = hass.states.get(config[CONF_ENTITY_ID])
    code_required = state.attributes.get(ATTR_CODE_ARM_REQUIRED) if state else False

    if config[CONF_TYPE] == "trigger" or (
        config[CONF_TYPE] != "disarm" and not code_required
    ):
        return {}

    return {"extra_fields": vol.Schema({vol.Optional(CONF_CODE): str})}
