"""Provides device conditions for remotes."""
from typing import Dict, List

import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.condition import ConditionCheckerType
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

CONDITION_SCHEMA = toggle_entity.CONDITION_SCHEMA.extend(
    {vol.Required(CONF_DOMAIN): DOMAIN}
)


@callback
def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> ConditionCheckerType:
    """Evaluate state based on configuration."""
    if config_validation:
        config = CONDITION_SCHEMA(config)
    return toggle_entity.async_condition_from_config(config)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> List[Dict[str, str]]:
    """List device conditions."""
    return await toggle_entity.async_get_conditions(hass, device_id, DOMAIN)


async def async_get_condition_capabilities(hass: HomeAssistant, config: dict) -> dict:
    """List condition capabilities."""
    return await toggle_entity.async_get_condition_capabilities(hass, config)
