"""Provides device automations for Cover."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.entity import get_supported_features
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN, CoverEntityFeature

# mypy: disallow-any-generics

POSITION_CONDITION_TYPES = {"is_position", "is_tilt_position"}
STATE_CONDITION_TYPES = {"is_open", "is_closed", "is_opening", "is_closing"}

POSITION_CONDITION_SCHEMA = vol.All(
    DEVICE_CONDITION_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
            vol.Required(CONF_TYPE): vol.In(POSITION_CONDITION_TYPES),
            vol.Optional(CONF_ABOVE): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
            vol.Optional(CONF_BELOW): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            ),
        }
    ),
    cv.has_at_least_one_key(CONF_BELOW, CONF_ABOVE),
)

STATE_CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): vol.In(STATE_CONDITION_TYPES),
    }
)

CONDITION_SCHEMA = vol.Any(POSITION_CONDITION_SCHEMA, STATE_CONDITION_SCHEMA)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Cover devices."""
    registry = er.async_get(hass)
    conditions: list[dict[str, str]] = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        supported_features = get_supported_features(hass, entry.entity_id)
        supports_open_close = supported_features & (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        )

        # Add conditions for each entity that belongs to this integration
        base_condition = {
            CONF_CONDITION: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.id,
        }

        if supports_open_close:
            conditions += [
                {**base_condition, CONF_TYPE: cond} for cond in STATE_CONDITION_TYPES
            ]
        if supported_features & CoverEntityFeature.SET_POSITION:
            conditions.append({**base_condition, CONF_TYPE: "is_position"})
        if supported_features & CoverEntityFeature.SET_TILT_POSITION:
            conditions.append({**base_condition, CONF_TYPE: "is_tilt_position"})

    return conditions


async def async_get_condition_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List condition capabilities."""
    if config[CONF_TYPE] not in ["is_position", "is_tilt_position"]:
        return {}

    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional(CONF_ABOVE, default=0): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                ),
                vol.Optional(CONF_BELOW, default=100): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                ),
            }
        )
    }


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    registry = er.async_get(hass)
    entity_id = er.async_resolve_entity_id(registry, config[CONF_ENTITY_ID])

    if config[CONF_TYPE] in STATE_CONDITION_TYPES:
        if config[CONF_TYPE] == "is_open":
            state = STATE_OPEN
        elif config[CONF_TYPE] == "is_closed":
            state = STATE_CLOSED
        elif config[CONF_TYPE] == "is_opening":
            state = STATE_OPENING
        elif config[CONF_TYPE] == "is_closing":
            state = STATE_CLOSING

        def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
            """Test if an entity is a certain state."""
            return condition.state(hass, entity_id, state)

        return test_is_state

    if config[CONF_TYPE] == "is_position":
        position_attr = "current_position"
    if config[CONF_TYPE] == "is_tilt_position":
        position_attr = "current_tilt_position"
    min_pos = config.get(CONF_ABOVE)
    max_pos = config.get(CONF_BELOW)

    @callback
    def check_numeric_state(
        hass: HomeAssistant, variables: TemplateVarsType = None
    ) -> bool:
        """Return whether the criteria are met."""
        return condition.async_numeric_state(
            hass, entity_id, max_pos, min_pos, attribute=position_attr
        )

    return check_numeric_state
