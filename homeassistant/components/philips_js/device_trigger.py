"""Provides device automations for control of device."""
from typing import List, Optional

import voluptuous as vol

from homeassistant.components.automation import AutomationActionType
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry, async_get_registry
from homeassistant.helpers.typing import ConfigType

from . import PhilipsTVDataUpdateCoordinator
from .const import DOMAIN

TRIGGER_TYPE_TURN_ON = "turn_on"

TRIGGER_TYPES = {TRIGGER_TYPE_TURN_ON}
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
            CONF_TYPE: TRIGGER_TYPE_TURN_ON,
        }
    )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: AutomationActionType,
    automation_info: dict,
) -> Optional[CALLBACK_TYPE]:
    """Attach a trigger."""
    registry: DeviceRegistry = await async_get_registry(hass)
    if config[CONF_TYPE] == TRIGGER_TYPE_TURN_ON:
        variables = {
            "trigger": {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": config[CONF_DEVICE_ID],
                "description": f"philips_js '{config[CONF_TYPE]}' event",
            }
        }

        device = registry.async_get(config[CONF_DEVICE_ID])
        for config_entry_id in device.config_entries:
            coordinator: PhilipsTVDataUpdateCoordinator = hass.data[DOMAIN].get(
                config_entry_id
            )
            if coordinator:
                return coordinator.turn_on.async_attach(action, variables)

    return None
