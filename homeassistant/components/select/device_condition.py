"""Provide the device conditions for Select."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import (
    async_get_entity_registry_entry_or_raise,
)
from homeassistant.const import (
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.entity import get_capability
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import ATTR_OPTIONS, CONF_OPTION, DOMAIN

# nypy: disallow-any-generics

CONDITION_TYPES = {"selected_option"}

CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
        vol.Required(CONF_OPTION): str,
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Select devices."""
    registry = er.async_get(hass)
    return [
        {
            CONF_CONDITION: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.id,
            CONF_TYPE: "selected_option",
        }
        for entry in er.async_entries_for_device(registry, device_id)
        if entry.domain == DOMAIN
    ]


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""

    registry = er.async_get(hass)
    entity_id = er.async_resolve_entity_id(registry, config[CONF_ENTITY_ID])

    @callback
    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        return condition.state(
            hass, entity_id, config[CONF_OPTION], config.get(CONF_FOR)
        )

    return test_is_state


async def async_get_condition_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List condition capabilities."""

    try:
        entry = async_get_entity_registry_entry_or_raise(hass, config[CONF_ENTITY_ID])
        options = get_capability(hass, entry.entity_id, ATTR_OPTIONS) or []
    except HomeAssistantError:
        options = []

    return {
        "extra_fields": vol.Schema(
            {
                vol.Required(CONF_OPTION): vol.In(options),
                vol.Optional(CONF_FOR): cv.positive_time_period_dict,
            }
        )
    }
