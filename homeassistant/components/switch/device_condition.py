"""Provides device conditions for switches."""
from typing import List
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.condition import ConditionCheckerType
from . import DOMAIN


CONDITION_SCHEMA = toggle_entity.CONDITION_SCHEMA.extend(
    {vol.Required(CONF_DOMAIN): DOMAIN}
)


def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> ConditionCheckerType:
    """Evaluate state based on configuration."""
    config = CONDITION_SCHEMA(config)
    return toggle_entity.async_condition_from_config(config, config_validation)


async def async_get_conditions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device conditions."""
    return await toggle_entity.async_get_conditions(hass, device_id, DOMAIN)
