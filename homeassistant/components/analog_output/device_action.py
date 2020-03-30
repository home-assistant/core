"""Provides device actions for analog_outputs."""
from typing import List

import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import ATTR_ENTITY_ID, CONF_DOMAIN, SERVICE_TURN_ON
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import ATTR_VALUE, ATTR_VALUE_PCT, DOMAIN

# ToDo: how to limit ATTR_VALUE with config min and max?
ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_DOMAIN): DOMAIN,
        vol.Optional(ATTR_VALUE): vol.Coerce(int),
        vol.Optional(ATTR_VALUE_PCT): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context,
) -> None:
    """Change state based on configuration."""
    data = {ATTR_ENTITY_ID: config[ATTR_ENTITY_ID]}
    if ATTR_VALUE_PCT in config:
        data[ATTR_VALUE_PCT] = config[ATTR_VALUE_PCT]
    if ATTR_VALUE in config:
        data[ATTR_VALUE] = config[ATTR_VALUE]

    await hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=context
    )


async def async_get_actions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device actions."""
    return await toggle_entity.async_get_actions(hass, device_id, DOMAIN)
