"""Provides device actions for Flo by Moen devices."""
from typing import List

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN as FLO_DOMAIN
from .services import (
    ATTR_DEVICE_ID,
    ATTR_LOCATION_ID,
    ATTR_REVERT_TO_MODE,
    ATTR_SLEEP_MINUTES,
    SERVICE_RUN_HEALTH_TEST,
    SERVICE_SET_AWAY_MODE,
    SERVICE_SET_HOME_MODE,
    SERVICE_SET_SLEEP_MODE,
    SYSTEM_MODE_HOME,
)

FLO_ACTION_TYPE_SERVICE_CALL = "service_call"

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {vol.Required(CONF_DOMAIN): FLO_DOMAIN, vol.Required(CONF_TYPE): str}
)

DEVICE_ACTIONS = [
    {CONF_TYPE: SERVICE_RUN_HEALTH_TEST, CONF_DOMAIN: FLO_DOMAIN},
    {CONF_TYPE: SERVICE_SET_AWAY_MODE, CONF_DOMAIN: FLO_DOMAIN},
    {CONF_TYPE: SERVICE_SET_HOME_MODE, CONF_DOMAIN: FLO_DOMAIN},
    {CONF_TYPE: SERVICE_SET_SLEEP_MODE, CONF_DOMAIN: FLO_DOMAIN},
]

DEVICE_ACTION_TYPES = {
    SERVICE_RUN_HEALTH_TEST: FLO_ACTION_TYPE_SERVICE_CALL,
    SERVICE_SET_AWAY_MODE: FLO_ACTION_TYPE_SERVICE_CALL,
    SERVICE_SET_HOME_MODE: FLO_ACTION_TYPE_SERVICE_CALL,
    SERVICE_SET_SLEEP_MODE: FLO_ACTION_TYPE_SERVICE_CALL,
}


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context,
) -> None:
    """Perform an action based on configuration."""
    await FLO_ACTION_TYPES[DEVICE_ACTION_TYPES[config[CONF_TYPE]]](
        hass, config, variables, context
    )


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions."""
    actions = DEVICE_ACTIONS[:]
    for action in actions:
        action[CONF_DEVICE_ID] = device_id
    return actions


async def _execute_service_based_action(
    hass: HomeAssistant,
    config: ACTION_SCHEMA,
    variables: TemplateVarsType,
    context: Context,
) -> None:
    action_type = config[CONF_TYPE]
    try:
        flo_device = await async_get_flo_device(hass, config[CONF_DEVICE_ID])
        if flo_device is None:
            return
    except (KeyError, AttributeError):
        return

    if action_type == SERVICE_RUN_HEALTH_TEST:
        service_data = {ATTR_DEVICE_ID: flo_device.id}
    else:
        service_data = {ATTR_LOCATION_ID: flo_device.location_id}

    if action_type == SERVICE_SET_SLEEP_MODE:
        service_data[ATTR_SLEEP_MINUTES] = 120
        service_data[ATTR_REVERT_TO_MODE] = SYSTEM_MODE_HOME

    await hass.services.async_call(
        FLO_DOMAIN, action_type, service_data, blocking=True, context=context
    )


async def async_get_flo_device(hass, device_id):
    """Get a Flo device for the given device registry id."""
    device_registry = await hass.helpers.device_registry.async_get_registry()
    registry_device = device_registry.async_get(device_id)
    devices = hass.data[FLO_DOMAIN]["devices"]
    flo_device_id = list(list(registry_device.identifiers)[0])[1]
    for device in devices:
        if device.id == flo_device_id:
            return device
    return None


FLO_ACTION_TYPES = {FLO_ACTION_TYPE_SERVICE_CALL: _execute_service_based_action}
