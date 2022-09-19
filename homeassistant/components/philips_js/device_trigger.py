"""Provides device automations for control of device."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import PhilipsTVDataUpdateCoordinator
from .const import DOMAIN

TRIGGER_TYPE_TURN_ON = "turn_on"

TRIGGER_TYPES = {TRIGGER_TYPE_TURN_ON}
TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers for device."""
    triggers = []
    triggers.append(
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: TRIGGER_TYPE_TURN_ON,
        }
    )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    trigger_data = trigger_info["trigger_data"]
    registry: dr.DeviceRegistry = dr.async_get(hass)
    if (trigger_type := config[CONF_TYPE]) == TRIGGER_TYPE_TURN_ON:
        variables = {
            "trigger": {
                **trigger_data,
                "platform": "device",
                "domain": DOMAIN,
                "device_id": config[CONF_DEVICE_ID],
                "description": f"philips_js '{trigger_type}' event",
            }
        }

        device = registry.async_get(config[CONF_DEVICE_ID])
        if device is None:
            raise HomeAssistantError(
                f"Device id {config[CONF_DEVICE_ID]} not found in registry"
            )
        for config_entry_id in device.config_entries:
            coordinator: PhilipsTVDataUpdateCoordinator = hass.data[DOMAIN].get(
                config_entry_id
            )
            if coordinator:
                return coordinator.turn_on.async_attach(action, variables)

    raise HomeAssistantError(f"Unhandled trigger type {trigger_type}")
