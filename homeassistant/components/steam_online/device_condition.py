"""Provide the device conditions for Steam."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import (
    condition,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import CONDITION_PRIMARY_GAME, CONF_ACCOUNT, DOMAIN

CONDITION_TYPES = {CONDITION_PRIMARY_GAME}

CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Steam devices."""
    # registry = er.async_get(hass)
    conditions = []

    base_condition = {
        CONF_CONDITION: "device",
        CONF_DEVICE_ID: device_id,
        CONF_DOMAIN: DOMAIN,
    }

    conditions += [{**base_condition, CONF_TYPE: cond} for cond in CONDITION_TYPES]

    return conditions


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""

    config_entry = hass.config_entries.async_get_entry(
        list(dr.async_get(hass).async_get(config[ATTR_DEVICE_ID]).config_entries)[0]
    )

    # Find the primary entity id that's linked to the account on initial setup
    primary_user_entity_id = next(
        entity
        for entity in er.async_entries_for_device(
            er.async_get(hass), config[ATTR_DEVICE_ID]
        )
        if entity.unique_id == config_entry.data[CONF_ACCOUNT]
    ).entity_id

    @callback
    def default_checker_method(
        hass: HomeAssistant, variables: TemplateVarsType
    ) -> bool:
        """Checker method for unmatched condition types."""
        return False

    @callback
    def test_is_same_game_as_primary(
        hass: HomeAssistant, variables: TemplateVarsType
    ) -> bool:
        """Test if an entity is a certain state."""
        trigger = variables.get("trigger")

        to_state: State = trigger.get("to_state")
        to_game = to_state.attributes.get("game_id")

        primary_game = hass.states.get(primary_user_entity_id).attributes.get("game_id")

        return primary_game is not None and primary_game == to_game

    if config[CONF_TYPE] == CONDITION_PRIMARY_GAME:
        test_method = test_is_same_game_as_primary
    else:
        test_method = default_checker_method

    return test_method
