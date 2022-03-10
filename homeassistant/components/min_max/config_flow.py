"""Config flow for Min/Max integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import selector

from . import get_unique_id
from .const import (
    ATTR_MAX_VALUE,
    CONF_ENTITY_IDS,
    CONF_ROUND_DIGITS,
    DOMAIN,
    SENSOR_TYPES,
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TYPE, default=SENSOR_TYPES[ATTR_MAX_VALUE]): vol.All(
            cv.string, vol.In(SENSOR_TYPES.values())
        ),
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITY_IDS): selector({"entity": {"multiple": True}}),
        vol.Optional(CONF_ROUND_DIGITS, default=2): vol.Coerce(int),
    }
)


class MinMaxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Min/Max."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

        if not user_input.get(CONF_NAME):
            user_input[CONF_NAME] = f"{user_input[CONF_TYPE]} sensor".capitalize()

        await self.async_set_unique_id(get_unique_id(user_input))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

    async_step_import = async_step_user
