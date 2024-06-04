"""Provides device automations for RFXCOM RFXtrx."""

from __future__ import annotations

from collections.abc import Callable

import voluptuous as vol

from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DATA_RFXOBJECT, DOMAIN
from .helpers import async_get_device_object

CONF_DATA = "data"
CONF_SUBTYPE = "subtype"

ACTION_TYPE_COMMAND = "send_command"
ACTION_TYPE_STATUS = "send_status"

ACTION_TYPES = {
    ACTION_TYPE_COMMAND,
    ACTION_TYPE_STATUS,
}

ACTION_SELECTION = {
    ACTION_TYPE_COMMAND: "COMMANDS",
    ACTION_TYPE_STATUS: "STATUS",
}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_SUBTYPE): str,
    }
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for RFXCOM RFXtrx devices."""

    try:
        device = async_get_device_object(hass, device_id)
    except ValueError:
        return []

    return [
        {
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: action_type,
            CONF_SUBTYPE: value,
        }
        for action_type in ACTION_TYPES
        if hasattr(device, action_type)
        for value in getattr(device, ACTION_SELECTION[action_type], {}).values()
    ]


def _get_commands(
    hass: HomeAssistant, device_id: str, action_type: str
) -> tuple[dict[str, str], Callable[..., None]]:
    device = async_get_device_object(hass, device_id)
    send_fun = getattr(device, action_type)
    commands = getattr(device, ACTION_SELECTION[action_type], {})
    return commands, send_fun


async def async_validate_action_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
    """Validate config."""
    config = ACTION_SCHEMA(config)
    commands, _ = _get_commands(hass, config[CONF_DEVICE_ID], config[CONF_TYPE])
    sub_type = config[CONF_SUBTYPE]

    if sub_type not in commands.values():
        raise InvalidDeviceAutomationConfig(
            f"Subtype {sub_type} not found in device commands {commands}"
        )

    return config


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    config = ACTION_SCHEMA(config)

    rfx = hass.data[DOMAIN][DATA_RFXOBJECT]
    commands, send_fun = _get_commands(hass, config[CONF_DEVICE_ID], config[CONF_TYPE])
    sub_type = config[CONF_SUBTYPE]

    for key, value in commands.items():
        if value == sub_type:
            await hass.async_add_executor_job(send_fun, rfx.transport, key)
            return
