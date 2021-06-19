"""Provide the device conditions for Z-Wave JS."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
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
    device_registry,
    entity_registry,
)
from homeassistant.helpers.config_validation import DEVICE_CONDITION_BASE_SCHEMA
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from . import DOMAIN
from .helpers import async_get_node_status_sensor_entity_id

CONDITION_TYPES = {"asleep", "awake", "dead", "alive"}

CONDITION_SCHEMA = DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Z-Wave JS devices."""

    ent_reg = entity_registry.async_get(hass)
    dev_reg = device_registry.async_get(hass)
    entity_id = async_get_node_status_sensor_entity_id(
        hass, device_id, ent_reg, dev_reg
    )
    base_condition = {
        CONF_CONDITION: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
        CONF_ENTITY_ID: entity_id,
    }

    conditions = [{**base_condition, CONF_TYPE: cond} for cond in CONDITION_TYPES]

    return conditions


@callback
def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    if config_validation:
        config = CONDITION_SCHEMA(config)

    state = config[CONF_TYPE]

    @callback
    def test_is_state(hass: HomeAssistant, variables: TemplateVarsType) -> bool:
        """Test if an entity is a certain state."""
        ent_reg = entity_registry.async_get(hass)
        entity_id = config[CONF_ENTITY_ID]

        return (
            (entity := ent_reg.async_get(entity_id)) is not None
            and not entity.disabled
            and condition.state(hass, entity_id, state)
        )

    return test_is_state
