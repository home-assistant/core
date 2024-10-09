"""Provide the device conditions for Steam."""

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
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import CONF_ACCOUNT, DOMAIN

# TODO specify your supported condition types.
CONDITION_TYPES = {"is_same_game_as_primary"}

CONDITION_SCHEMA = cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(CONDITION_TYPES),
    }
)


async def async_get_conditions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device conditions for Steam devices."""
    registry = er.async_get(hass)
    conditions = []

    # Get all the integrations entities for this device
    for entry in er.async_entries_for_device(registry, device_id):
        if entry.platform != DOMAIN:
            continue

        # Add conditions for each entity that belongs to this integration
        # TODO add your own conditions.
        base_condition = {
            CONF_CONDITION: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_ENTITY_ID: entry.entity_id,
        }

        conditions += [{**base_condition, CONF_TYPE: cond} for cond in CONDITION_TYPES]

    return conditions


@callback
def async_condition_from_config(
    hass: HomeAssistant, config: ConfigType
) -> condition.ConditionCheckerType:
    """Create a function to test a device condition."""
    # print("\033[96m  async_condition_from_config ::", config, "\033[0m")

    config_entry = hass.config_entries.async_get_entry(
        er.async_get(hass).async_get(config[ATTR_ENTITY_ID]).config_entry_id
    )
    primary_user = config_entry.data[CONF_ACCOUNT]
    primary_user_entity_id = f"sensor.steam_{primary_user}"

    @callback
    def test_is_same_game_as_primary(
        hass: HomeAssistant, variables: TemplateVarsType
    ) -> bool:
        """Test if an entity is a certain state."""

        event_game = hass.states.get(config[ATTR_ENTITY_ID]).attributes.get("game_id")
        primary_game = hass.states.get(primary_user_entity_id).attributes.get("game_id")

        is_same_game_as_primary = (
            primary_game is not None and primary_game == event_game
        )

        print(
            "\n\033[96m  test_is_state :: primary user game",
            primary_game,
            "event game",
            event_game,
            " ===> ",
            is_same_game_as_primary,
            "\033[0m\n",
        )

        return is_same_game_as_primary

    return test_is_same_game_as_primary
