"""Provides device automations for control of device."""
from typing import List

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry, async_get_registry
from homeassistant.helpers.typing import ConfigType

from . import LOGGER, PhilipsTVDataUpdateCoordinator
from .const import DOMAIN

TRIGGER_TYPES = {"turn_on"}
TRIGGER_SCHEMA = TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device triggers for device."""
    triggers = []
    triggers.append(
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "turn_on",
        }
    )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    registry: DeviceRegistry = await async_get_registry(hass)
    device = registry.async_get(config[CONF_DEVICE_ID])
    if device is None:
        LOGGER.error(
            "Unable to find device %s for device trigger", config[CONF_DEVICE_ID]
        )
        return

    variables = {
        "trigger": {
            "platform": config[CONF_PLATFORM],
            "description": f"trigger '{config[CONF_TYPE]}'",
        }
    }

    for config_entry_id in device.config_entries:
        coordinator: PhilipsTVDataUpdateCoordinator = hass.data[DOMAIN].get(
            config_entry_id
        )
        if coordinator:
            return coordinator.async_attach_turn_on_action(action, variables)
