"""Provides device actions for Select."""
from __future__ import annotations

from contextlib import suppress

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
from homeassistant.helpers.entity import get_capability
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import (
    ATTR_CYCLE,
    ATTR_OPTION,
    ATTR_OPTIONS,
    CONF_CYCLE,
    CONF_OPTION,
    DOMAIN,
    SERVICE_SELECT_FIRST,
    SERVICE_SELECT_LAST,
    SERVICE_SELECT_NEXT,
    SERVICE_SELECT_OPTION,
    SERVICE_SELECT_PREVIOUS,
)

ACTION_SCHEMA = vol.Any(
    cv.DEVICE_ACTION_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): SERVICE_SELECT_FIRST,
            vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        }
    ),
    cv.DEVICE_ACTION_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): SERVICE_SELECT_LAST,
            vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        }
    ),
    cv.DEVICE_ACTION_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): SERVICE_SELECT_NEXT,
            vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
            vol.Optional(CONF_CYCLE, default=True): cv.boolean,
        }
    ),
    cv.DEVICE_ACTION_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): SERVICE_SELECT_PREVIOUS,
            vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
            vol.Optional(CONF_CYCLE, default=True): cv.boolean,
        }
    ),
    cv.DEVICE_ACTION_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_TYPE): SERVICE_SELECT_OPTION,
            vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
            vol.Required(CONF_OPTION): cv.string,
        }
    ),
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for Select devices."""
    registry = entity_registry.async_get(hass)
    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
            CONF_TYPE: service_conf_type,
        }
        for service_conf_type in (
            SERVICE_SELECT_FIRST,
            SERVICE_SELECT_LAST,
            SERVICE_SELECT_NEXT,
            SERVICE_SELECT_OPTION,
            SERVICE_SELECT_PREVIOUS,
        )
        for entry in entity_registry.async_entries_for_device(registry, device_id)
        if entry.domain == DOMAIN
    ]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}
    if config[CONF_TYPE] == SERVICE_SELECT_OPTION:
        service_data[ATTR_OPTION] = config[CONF_OPTION]
    if config[CONF_TYPE] in {SERVICE_SELECT_NEXT, SERVICE_SELECT_PREVIOUS}:
        service_data[ATTR_CYCLE] = config[CONF_CYCLE]

    await hass.services.async_call(
        DOMAIN,
        config[CONF_TYPE],
        service_data,
        blocking=True,
        context=context,
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    if config[CONF_TYPE] in {SERVICE_SELECT_NEXT, SERVICE_SELECT_PREVIOUS}:
        return {
            "extra_fields": vol.Schema(
                {vol.Optional(CONF_CYCLE, default=True): cv.boolean}
            )
        }

    if config[CONF_TYPE] == SERVICE_SELECT_OPTION:
        options: list[str] = []
        with suppress(HomeAssistantError):
            options = get_capability(hass, config[CONF_ENTITY_ID], ATTR_OPTIONS) or []
        return {
            "extra_fields": vol.Schema({vol.Required(CONF_OPTION): vol.In(options)})
        }

    return {}
