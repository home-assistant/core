"""Provides device automations for Cover."""
from typing import List, Optional

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from . import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
)

CMD_ACTION_TYPES = {"open", "close", "stop", "open_tilt", "close_tilt"}
POSITION_ACTION_TYPES = {"set_position", "set_tilt_position"}

CMD_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(CMD_ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
    }
)

POSITION_ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(POSITION_ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_domain(DOMAIN),
        vol.Optional("position", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)

ACTION_SCHEMA = vol.Any(CMD_ACTION_SCHEMA, POSITION_ACTION_SCHEMA)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions for Cover devices."""
    registry = await entity_registry.async_get_registry(hass)
    actions = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        state = hass.states.get(entry.entity_id)
        if not state or ATTR_SUPPORTED_FEATURES not in state.attributes:
            continue

        supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]

        # Add actions for each entity that belongs to this integration
        if supported_features & SUPPORT_SET_POSITION:
            actions.append(
                {
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "set_position",
                }
            )
        else:
            if supported_features & SUPPORT_OPEN:
                actions.append(
                    {
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "open",
                    }
                )
            if supported_features & SUPPORT_CLOSE:
                actions.append(
                    {
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "close",
                    }
                )
            if supported_features & SUPPORT_STOP:
                actions.append(
                    {
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "stop",
                    }
                )

        if supported_features & SUPPORT_SET_TILT_POSITION:
            actions.append(
                {
                    CONF_DEVICE_ID: device_id,
                    CONF_DOMAIN: DOMAIN,
                    CONF_ENTITY_ID: entry.entity_id,
                    CONF_TYPE: "set_tilt_position",
                }
            )
        else:
            if supported_features & SUPPORT_OPEN_TILT:
                actions.append(
                    {
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "open_tilt",
                    }
                )
            if supported_features & SUPPORT_CLOSE_TILT:
                actions.append(
                    {
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_ENTITY_ID: entry.entity_id,
                        CONF_TYPE: "close_tilt",
                    }
                )

    return actions


async def async_get_action_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List action capabilities."""
    if config[CONF_TYPE] not in POSITION_ACTION_TYPES:
        return {}

    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional("position", default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                )
            }
        )
    }


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Optional[Context]
) -> None:
    """Execute a device action."""
    config = ACTION_SCHEMA(config)

    service_data = {ATTR_ENTITY_ID: config[CONF_ENTITY_ID]}

    if config[CONF_TYPE] == "open":
        service = SERVICE_OPEN_COVER
    elif config[CONF_TYPE] == "close":
        service = SERVICE_CLOSE_COVER
    elif config[CONF_TYPE] == "stop":
        service = SERVICE_STOP_COVER
    elif config[CONF_TYPE] == "open_tilt":
        service = SERVICE_OPEN_COVER_TILT
    elif config[CONF_TYPE] == "close_tilt":
        service = SERVICE_CLOSE_COVER_TILT
    elif config[CONF_TYPE] == "set_position":
        service = SERVICE_SET_COVER_POSITION
        service_data[ATTR_POSITION] = config["position"]
    elif config[CONF_TYPE] == "set_tilt_position":
        service = SERVICE_SET_COVER_TILT_POSITION
        service_data[ATTR_TILT_POSITION] = config["position"]

    await hass.services.async_call(
        DOMAIN, service, service_data, blocking=True, context=context
    )
