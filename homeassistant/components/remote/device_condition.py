"""Provides device conditions for remotes."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import toggle_entity
from homeassistant.const import CONF_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.condition import ConditionCheckerType
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN

# mypy: disallow-any-generics

CONDITION_SCHEMA = toggle_entity.CONDITION_SCHEMA.extend(
    {vol.Required(CONF_DOMAIN): DOMAIN}
)


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> ConditionCheckerType:
    """Evaluate state based on configuration."""
    return toggle_entity.async_condition_from_config(hass, config)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions."""
    return await toggle_entity.async_get_conditions(hass, device_id, DOMAIN)


async def async_get_condition_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List condition capabilities."""
    return await toggle_entity.async_get_condition_capabilities(hass, config)
