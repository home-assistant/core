"""Provides device triggers for Blue Current."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
)
from homeassistant.components.homeassistant.triggers import state
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

ACTIVITY_TYPES = {
    "available",
    "charging",
    "unavailable",
    "error",
    "offline",
}
VEHICLE_STATUS_TYPES = {
    "standby",
    "vehicle_detected",
    "ready",
    "no_power",
    "vehicle_error",
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(ACTIVITY_TYPES.union(VEHICLE_STATUS_TYPES)),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for blue current devices."""
    triggers = []
    registry = dr.async_get(hass)

    if (device := registry.async_get(device_id)) is None:
        raise InvalidDeviceAutomationConfig(f"Device ID {device_id} is not valid")

    evse_id = list(device.identifiers)[0][1].lower()

    base_trigger = {
        CONF_PLATFORM: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    triggers += [
        {
            **base_trigger,
            CONF_TYPE: t,
            CONF_ENTITY_ID: f"sensor.{evse_id}_activity",
        }
        for t in ACTIVITY_TYPES
    ]

    triggers += [
        {
            **base_trigger,
            CONF_TYPE: t,
            CONF_ENTITY_ID: f"sensor.{evse_id}_vehicle_status",
        }
        for t in VEHICLE_STATUS_TYPES
    ]
    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    state_config = {
        state.CONF_PLATFORM: "state",
        CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state.CONF_TO: config[CONF_TYPE],
    }

    state_config = await state.async_validate_trigger_config(hass, state_config)
    return await state.async_attach_trigger(
        hass, state_config, action, trigger_info, platform_type="device"
    )
