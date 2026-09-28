"""Provides device automations for Cover."""

import probatio

from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_TYPE,
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

from . import CoverEntityFeature, CoverEntityStateAttribute, CoverState
from .const import DOMAIN

# mypy: disallow-any-generics

POSITION_CONDITION_TYPES = {"is_position", "is_tilt_position"}
STATE_CONDITION_TYPES = {"is_open", "is_closed", "is_opening", "is_closing"}

POSITION_CONDITION_SCHEMA = probatio.All(
    DEVICE_CONDITION_BASE_SCHEMA.extend(
        {
            probatio.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
            probatio.Required(CONF_TYPE): probatio.In(POSITION_CONDITION_TYPES),
            probatio.Optional(CONF_ABOVE): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            ),
            probatio.Optional(CONF_BELOW): probatio.All(
                probatio.Coerce(int), probatio.Range(min=0, max=100)
            ),
        }
    ),
    cv.has_at_least_one_key(CONF_BELOW, CONF_ABOVE),
)

STATE_CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        probatio.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        probatio.Required(CONF_TYPE): probatio.In(STATE_CONDITION_TYPES),
    }
)

CONDITION_SCHEMA = probatio.Any(POSITION_CONDITION_SCHEMA, STATE_CONDITION_SCHEMA)


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
) -> dict[str, probatio.Schema]:
    """List condition capabilities."""
    if config[CONF_TYPE] not in ["is_position", "is_tilt_position"]:
        return {}

    return {
        "extra_fields": probatio.Schema(
            {
                probatio.Optional(CONF_ABOVE, default=0): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=100)
                ),
                probatio.Optional(CONF_BELOW, default=100): probatio.All(
                    probatio.Coerce(int), probatio.Range(min=0, max=100)
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
            state = CoverState.OPEN
        elif config[CONF_TYPE] == "is_closed":
            state = CoverState.CLOSED
        elif config[CONF_TYPE] == "is_opening":
            state = CoverState.OPENING
        elif config[CONF_TYPE] == "is_closing":
            state = CoverState.CLOSING

        def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
            """Test if an entity is a certain state."""
            return condition.state(hass, entity_id, state)

        return test_is_state

    if config[CONF_TYPE] == "is_position":
        position_attr = CoverEntityStateAttribute.CURRENT_POSITION
    if config[CONF_TYPE] == "is_tilt_position":
        position_attr = CoverEntityStateAttribute.CURRENT_TILT_POSITION
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
