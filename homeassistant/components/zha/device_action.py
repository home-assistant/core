"""Provides device actions for ZHA devices."""
from typing import List

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN
from .api import SERVICE_WARNING_DEVICE_SQUAWK, SERVICE_WARNING_DEVICE_WARN
from .core.const import CHANNEL_IAS_WD
from .core.helpers import async_get_zha_device

ACTION_SQUAWK = "squawk"
ACTION_WARN = "warn"
ATTR_IEEE = "ieee"
ATTR_DATA = "data"

SERVICE_NAMES = {
    ACTION_SQUAWK: SERVICE_WARNING_DEVICE_SQUAWK,
    ACTION_WARN: SERVICE_WARNING_DEVICE_WARN,
}

ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Required(CONF_TYPE): vol.In([ACTION_SQUAWK, ACTION_WARN]),
    }
)


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context,
) -> None:
    """Perform an action based on configuration."""
    config = ACTION_SCHEMA(config)
    action_type = config[CONF_TYPE]
    service_name = SERVICE_NAMES[action_type]
    zha_device = await async_get_zha_device(hass, config[CONF_DEVICE_ID])

    service_action = {
        service.CONF_SERVICE: "{}.{}".format(DOMAIN, service_name),
        ATTR_DATA: {ATTR_IEEE: str(zha_device.ieee)},
    }

    await service.async_call_from_config(
        hass, service_action, blocking=True, variables=variables, context=context
    )


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions."""
    zha_device = await async_get_zha_device(hass, device_id)
    if CHANNEL_IAS_WD in zha_device.cluster_channels:
        return [
            {CONF_TYPE: ACTION_SQUAWK, CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN},
            {CONF_TYPE: ACTION_WARN, CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN},
        ]
    return []
