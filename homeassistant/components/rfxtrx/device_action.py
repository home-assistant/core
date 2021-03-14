"""Provides device automations for RFXCOM RFXtrx."""
from typing import List, Optional

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
import homeassistant.helpers.config_validation as cv

from . import DATA_RFXOBJECT, DOMAIN
from .helpers import async_get_device_object

CONF_DATA = "data"

ACTION_TYPE_COMMAND = "send_command"

ACTION_TYPES = {
    ACTION_TYPE_COMMAND,
}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Required(CONF_DATA): int,
    }
)


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions for RFXCOM RFXtrx devices."""
    actions = []

    device = async_get_device_object(hass, device_id)
    if device:
        for action_type in ACTION_TYPES:
            if hasattr(device, action_type):
                actions.append(
                    {
                        CONF_DEVICE_ID: device_id,
                        CONF_DOMAIN: DOMAIN,
                        CONF_TYPE: action_type,
                    }
                )

    return actions


async def async_get_action_capabilities(hass, config):
    """List action capabilities."""

    device = async_get_device_object(hass, config[CONF_DEVICE_ID])
    if config[CONF_TYPE] == ACTION_TYPE_COMMAND:
        values = getattr(device, "COMMANDS")
        if values:
            data_schema = vol.In(values)
        else:
            data_schema = vol.Range(0, 255)
        return {"extra_fields": vol.Schema({vol.Required(CONF_DATA): data_schema})}

    return {}


async def async_call_action_from_config(
    hass: HomeAssistant, config: dict, variables: dict, context: Optional[Context]
) -> None:
    """Execute a device action."""
    config = ACTION_SCHEMA(config)

    rfx = hass.data[DOMAIN][DATA_RFXOBJECT]
    device = async_get_device_object(hass, config[CONF_DEVICE_ID])

    send_fun = getattr(device, config[CONF_TYPE])

    if config[CONF_TYPE] == ACTION_TYPE_COMMAND:
        await hass.async_add_executor_job(send_fun, rfx.transport, config[CONF_DATA])
