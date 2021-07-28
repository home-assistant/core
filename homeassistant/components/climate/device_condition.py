"""Provide the device automations for Climate."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, HomeAssistantError, callback
from homeassistant.helpers import condition, config_validation as cv, entity_registry
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.entity import get_capability, get_supported_features
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN, const

CONDITION_TYPES = {"is_hvac_mode", "is_preset_mode"}

HVAC_MODE_CONDITION = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): "is_hvac_mode",
        vol.Required(const.ATTR_HVAC_MODE): vol.In(const.HVAC_MODES),
    }
)

PRESET_MODE_CONDITION = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): "is_preset_mode",
        vol.Required(const.ATTR_PRESET_MODE): str,
    }
)

CONDITION_SCHEMA = vol.Any(HVAC_MODE_CONDITION, PRESET_MODE_CONDITION)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Climate devices."""
    registry = await entity_registry.async_get_registry(hass)
    conditions = []

    # Get all the integrations entities for this device
    for entry in entity_registry.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        supported_features = get_supported_features(hass, entry.entity_id)

        base_condition = {
            CONF_CONDITION: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        conditions.append({**base_condition, CONF_TYPE: "is_hvac_mode"})

        if supported_features & const.SUPPORT_PRESET_MODE:
            conditions.append({**base_condition, CONF_TYPE: "is_preset_mode"})

    return conditions


@callback
def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config_validation:
        config = CONDITION_SCHEMA(config)

    if config[CONF_TYPE] == "is_hvac_mode":
        attribute = const.ATTR_HVAC_MODE
    else:
        attribute = const.ATTR_PRESET_MODE

    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        state = hass.states.get(config[ATTR_ENTITY_ID])
        return state.attributes.get(attribute) == config[attribute] if state else False

    return test_is_state


async def async_get_condition_capabilities(hass, config):
    """List condition capabilities."""
    condition_type = config[CONF_TYPE]

    fields = {}

    if condition_type == "is_hvac_mode":
        try:
            hvac_modes = (
                get_capability(hass, config[ATTR_ENTITY_ID], const.ATTR_HVAC_MODES)
                or []
            )
        except HomeAssistantError:
            hvac_modes = []
        fields[vol.Required(const.ATTR_HVAC_MODE)] = vol.In(hvac_modes)

    elif condition_type == "is_preset_mode":
        try:
            preset_modes = (
                get_capability(hass, config[ATTR_ENTITY_ID], const.ATTR_PRESET_MODES)
                or []
            )
        except HomeAssistantError:
            preset_modes = []
        fields[vol.Required(const.ATTR_PRESET_MODE)] = vol.In(preset_modes)

    return {"extra_fields": vol.Schema(fields)}
