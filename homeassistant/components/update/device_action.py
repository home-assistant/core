"""Provides device actions for update entities."""
from __future__ import annotations

from typing import Final

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
from homeassistant.helpers.entity import get_supported_features
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_BACKUP,
    DOMAIN,
    SERVICE_INSTALL,
    SERVICE_SKIP,
    UpdateEntityFeature,
)

ACTION_TYPES: Final[set[str]] = {"install", "skip"}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Optional("backup"): cv.boolean,
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for update devices."""
    registry = await entity_registry.async_get_registry(hass)
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

        # Add actions for each entity that belongs to this integration
        if supported_features & UpdateEntityFeature.INSTALL:
            actions.append({**base_action, CONF_TYPE: "install"})
        actions.append({**base_action, CONF_TYPE: "skip"})

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    service = SERVICE_INSTALL
    if config[CONF_TYPE] == "skip":
        service = SERVICE_SKIP

    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}
    if "backup" in config:
        service_data[ATTR_BACKUP] = config["backup"]

    await hass.services.async_call(
        DOMAIN,
        service,
        service_data,
        blocking=True,
        context=context,
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""
    if config[CONF_TYPE] != "install":
        return {}

    try:
        supported_features = get_supported_features(hass, config[ATTR_ENTITY_ID])
    except HomeAssistantError:
        supported_features = 0

    extra_fields = {}

    if supported_features & UpdateEntityFeature.BACKUP:
        extra_fields[vol.Optional(ATTR_BACKUP)] = cv.boolean

    return {"extra_fields": vol.Schema(extra_fields)} if extra_fields else {}
