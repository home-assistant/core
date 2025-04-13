"""Provides device actions for Number."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import async_validate_entity_schema
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import ATTR_VALUE, DOMAIN, SERVICE_SET_VALUE

ATYP_SET_VALUE = "set_value"

_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): ATYP_SET_VALUE,
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(ATTR_VALUE): vol.Coerce(float),
    }
)


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    return async_validate_entity_schema(hass, config, _ACTION_SCHEMA)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for Number."""
    registry = er.async_get(hass)
    actions: list[dict[str, str]] = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        actions.append(
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_ENTITY_ID: entry.id,
                CONF_TYPE: ATYP_SET_VALUE,
            }
        )

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: config[CONF_ENTITY_ID],
            ATTR_VALUE: config[ATTR_VALUE],
        },
        blocking=True,
        context=context,
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    fields = {vol.Required(ATTR_VALUE): vol.Coerce(float)}

    return {"extra_fields": vol.Schema(fields)}
