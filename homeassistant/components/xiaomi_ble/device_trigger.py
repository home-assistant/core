"""Provides device triggers for Xiaomi BLE."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_EVENT_PROPERTIES,
    DOMAIN,
    EVENT_PROPERTIES,
    EVENT_TYPE,
    XIAOMI_BLE_EVENT,
)

MOTION_DEVICE_TRIGGERS = [
    {CONF_TYPE: "motion_detected", CONF_EVENT_PROPERTIES: None},
]

MOTION_DEVICE_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(
            [trigger[CONF_TYPE] for trigger in MOTION_DEVICE_TRIGGERS]
        ),
        vol.Optional(CONF_EVENT_PROPERTIES): vol.In(
            [trigger[CONF_EVENT_PROPERTIES] for trigger in MOTION_DEVICE_TRIGGERS]
        ),
    }
)


@dataclass
class TriggerModelData:
    """Data class for trigger model data."""

    triggers: list[dict[str, Any]]
    schema: vol.Schema


MODEL_DATA = {
    "MUE4094RT": TriggerModelData(
        triggers=MOTION_DEVICE_TRIGGERS, schema=MOTION_DEVICE_SCHEMA
    )
}


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate trigger config."""
    device_id = config[CONF_DEVICE_ID]
    if model_data := _async_trigger_model_data(hass, device_id):
        return model_data.schema(config)
    return config


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List a list of triggers for Xiaomi BLE devices."""

    # Check if device is a model supporting device triggers.
    if not (model_data := _async_trigger_model_data(hass, device_id)):
        return []
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            **trigger,
        }
        for trigger in model_data.triggers
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""

    event_data = {
        CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        EVENT_TYPE: config[CONF_TYPE],
        EVENT_PROPERTIES: config[CONF_EVENT_PROPERTIES],
    }
    return await event_trigger.async_attach_trigger(
        hass,
        event_trigger.TRIGGER_SCHEMA(
            {
                event_trigger.CONF_PLATFORM: CONF_EVENT,
                event_trigger.CONF_EVENT_TYPE: XIAOMI_BLE_EVENT,
                event_trigger.CONF_EVENT_DATA: event_data,
            }
        ),
        action,
        trigger_info,
        platform_type="device",
    )


def _async_trigger_model_data(
    hass: HomeAssistant, device_id: str
) -> TriggerModelData | None:
    """Get available triggers for a given model."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    if device and device.model and (model_data := MODEL_DATA.get(device.model)):
        return model_data
    return None
