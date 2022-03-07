"""Config flow for Min/Max integration."""
from __future__ import annotations

from typing import Any, cast

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import helper_config_entry_flow, selector

from .const import CONF_ENTITY_IDS, CONF_ROUND_DIGITS, DOMAIN

_STATISTIC_MEASURES = ["last", "max", "mean", "min", "median"]

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_IDS): selector.selector(
            {"entity": {"domain": "sensor", "multiple": True}}
        ),
        vol.Required(CONF_TYPE): selector.selector(
            {"select": {"options": _STATISTIC_MEASURES}}
        ),
        vol.Required(CONF_ROUND_DIGITS, default=2): selector.selector(
            {"number": {"min": 0, "max": 6}}
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required("name"): selector.selector({"text": {}}),
    }
).extend(OPTIONS_SCHEMA.schema)

STEPS = {
    "init": CONFIG_SCHEMA,
    "options": OPTIONS_SCHEMA,
}


class ConfigFlowHandler(
    helper_config_entry_flow.HelperConfigFlowHandler, domain=DOMAIN
):
    """Handle a config or options flow for Min/Max."""

    steps = STEPS

    def async_config_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return config entry title."""
        return cast(str, user_input["name"]) if "name" in user_input else ""

    @staticmethod
    def async_initial_options_step(config_entry: ConfigEntry) -> str:
        """Return initial options step."""
        return "options"

    async def async_validate_input(
        self, hass: HomeAssistant, step_id: str, user_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate user input."""
        if not self._config_entry:
            return user_input

        selected_entities = user_input[CONF_ENTITY_IDS]
        return helper_config_entry_flow.async_own_entity_not_selected(
            hass,
            user_input,
            self._config_entry,
            DOMAIN,
            SENSOR_DOMAIN,
            selected_entities,
        )
