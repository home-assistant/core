"""Provides device actions for YoLink."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_SENSOR_TYPE,
    CONF_TYPE,
    SERVICE_CLOSE,
    SERVICE_OPEN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

# TODO specify your supported action types.
ACTION_TYPES = {"turn_on", "turn_off", "open", "close"}

YL_DEVICE_ID = "yl_device_id"

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(YL_DEVICE_ID): str,
    }
)

__LOGGER = logging.getLogger(__name__)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict]:
    """List device actions for YoLink devices."""

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)
    identifiers = list(device.identifiers)[0]
    actions: list[dict] = []
    if device.model in ["THSensor", "MotionSensor"] or device.manufacturer != "YoLink":
        return actions

    registry = await entity_registry.async_get_registry(hass)

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.platform != DOMAIN:
            continue
        base_action = {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
            YL_DEVICE_ID: list(identifiers)[1],
        }

        if device.model in ["Outlet", "Siren"]:
            actions.append({**base_action, CONF_TYPE: "turn_on"})
            actions.append({**base_action, CONF_TYPE: "turn_off"})
            break
        if device.model in ["DoorSensor"]:
            actions.append({**base_action, CONF_TYPE: "open"})
            actions.append({**base_action, CONF_TYPE: "close"})
            break

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Context | None
) -> None:
    """Execute a device action."""
    device_id = config[ATTR_DEVICE_ID]
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(device_id)
    service = None
    if device.model == "Siren":
        if config[CONF_TYPE] == SERVICE_TURN_ON:
            service = "siren_turn_on"
        elif config[CONF_TYPE] == SERVICE_TURN_OFF:
            service = "siren_turn_off"
    elif device.model == "Outlet":
        if config[CONF_TYPE] == SERVICE_TURN_ON:
            service = "outlet_turn_on"
        elif config[CONF_TYPE] == SERVICE_TURN_OFF:
            service = "outlet_turn_off"
    elif device.model == "DoorSensor":
        if config[CONF_TYPE] == SERVICE_OPEN:
            service = "door_open"
        elif config[CONF_TYPE] == SERVICE_CLOSE:
            service = "door_close"
    if service:
        service_data = {
            ATTR_ENTITY_ID: config[CONF_ENTITY_ID],
            ATTR_DEVICE_ID: config[CONF_DEVICE_ID],
            YL_DEVICE_ID: config[YL_DEVICE_ID],
            CONF_SENSOR_TYPE: device.model,
        }
        await hass.services.async_call(
            DOMAIN, service, service_data, blocking=True, context=context
        )
