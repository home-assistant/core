"""Provide the device automations for Climate."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import (
    async_get_entity_registry_entry_or_raise,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
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
from homeassistant.helpers.entity import get_capability, get_supported_features
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN, const

CONDITION_TYPES = {"is_hvac_mode", "is_preset_mode"}

HVAC_MODE_CONDITION = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): "is_hvac_mode",
        vol.Required(const.ATTR_HVAC_MODE): vol.In(const.HVAC_MODES),
    }
)

PRESET_MODE_CONDITION = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): "is_preset_mode",
        vol.Required(const.ATTR_PRESET_MODE): str,
    }
)

CONDITION_SCHEMA = vol.Any(HVAC_MODE_CONDITION, PRESET_MODE_CONDITION)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Climate devices."""
    registry = er.async_get(hass)
    conditions = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        supported_features = get_supported_features(hass, entry.entity_id)

        base_condition = {
            CONF_CONDITION: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.id,
        }

        conditions.append({**base_condition, CONF_TYPE: "is_hvac_mode"})

        if supported_features & const.ClimateEntityFeature.PRESET_MODE:
            conditions.append({**base_condition, CONF_TYPE: "is_preset_mode"})

    return conditions


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""

    registry = er.async_get(hass)
    entity_id = er.async_resolve_entity_id(registry, config[ATTR_ENTITY_ID])

    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        if not entity_id or (state := hass.states.get(entity_id)) is None:
            return False

        if config[CONF_TYPE] == "is_hvac_mode":
            return bool(state.state == config[const.ATTR_HVAC_MODE])

        return bool(
            state.attributes.get(const.ATTR_PRESET_MODE)
            == config[const.ATTR_PRESET_MODE]
        )

    return test_is_state


async def async_get_condition_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List condition capabilities."""
    condition_type = config[CONF_TYPE]

    fields = {}

    if condition_type == "is_hvac_mode":
        try:
            entry = async_get_entity_registry_entry_or_raise(
                hass, config[CONF_ENTITY_ID]
            )
            hvac_modes = (
                get_capability(hass, entry.entity_id, const.ATTR_HVAC_MODES) or []
            )
        except HomeAssistantError:
            hvac_modes = []
        fields[vol.Required(const.ATTR_HVAC_MODE)] = vol.In(hvac_modes)

    elif condition_type == "is_preset_mode":
        try:
            entry = async_get_entity_registry_entry_or_raise(
                hass, config[CONF_ENTITY_ID]
            )
            preset_modes = (
                get_capability(hass, entry.entity_id, const.ATTR_PRESET_MODES) or []
            )
        except HomeAssistantError:
            preset_modes = []
        fields[vol.Required(const.ATTR_PRESET_MODE)] = vol.In(preset_modes)

    return {"extra_fields": vol.Schema(fields)}
