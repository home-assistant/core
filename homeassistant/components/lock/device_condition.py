"""Provides device automations for Lock."""

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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN, LockState

# mypy: disallow-any-generics

CONDITION_TYPES = {
    "is_jammed",
    "is_locked",
    "is_locking",
    "is_open",
    "is_opening",
    "is_unlocked",
    "is_unlocking",
}

CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Lock devices."""
    registry = er.async_get(hass)
    conditions = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.domain != DOMAIN:
            continue

        # Add conditions for each entity that belongs to this integration
        base_condition = {
            CONF_CONDITION: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.id,
        }

        conditions += [{**base_condition, CONF_TYPE: cond} for cond in CONDITION_TYPES]

    return conditions


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config[CONF_TYPE] == "is_jammed":
        state = LockState.JAMMED
    elif config[CONF_TYPE] == "is_opening":
        state = LockState.OPENING
    elif config[CONF_TYPE] == "is_locking":
        state = LockState.LOCKING
    elif config[CONF_TYPE] == "is_open":
        state = LockState.OPEN
    elif config[CONF_TYPE] == "is_unlocking":
        state = LockState.UNLOCKING
    elif config[CONF_TYPE] == "is_locked":
        state = LockState.LOCKED
    else:
        state = LockState.UNLOCKED

    registry = er.async_get(hass)
    entity_id = er.async_resolve_entity_id(registry, config[ATTR_ENTITY_ID])

    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        return condition.state(hass, entity_id, state)

    return test_is_state
