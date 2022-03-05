"""Config flow for Switch integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_METHOD, TIME_HOURS
from homeassistant.core import split_entity_id
from homeassistant.helpers import (
    entity_registry as er,
    helper_config_entry_flow,
    selector,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ROUND_DIGITS,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DEFAULT_ROUND,
    DOMAIN,
    INTEGRATION_METHOD,
    TRAPEZOIDAL_METHOD,
    UNIT_PREFIXES,
    UNIT_TIME,
)

STEPS = {
    "init": vol.Schema(
        {
            vol.Required(CONF_SOURCE_SENSOR): selector.selector(
                {"entity": {"domain": "sensor"}}
            ),
            vol.Optional(CONF_ROUND_DIGITS, default=DEFAULT_ROUND): vol.Coerce(int),
            vol.Optional(CONF_UNIT_PREFIX, default=None): vol.In(
                list(UNIT_PREFIXES.keys())
            ),
            vol.Optional(CONF_UNIT_TIME, default=TIME_HOURS): vol.In(
                list(UNIT_TIME.keys())
            ),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_METHOD, default=TRAPEZOIDAL_METHOD): vol.In(
                INTEGRATION_METHOD
            ),
        }
    )
}


class ConfigFlowHandler(
    helper_config_entry_flow.HelperConfigFlowHandler, domain=DOMAIN
):
    """Handle a config or options flow for Switch Light."""

    steps = STEPS

    def async_config_entry_title(self, user_input: dict[str, Any]) -> str:
        """Return config entry title."""
        registry = er.async_get(self.hass)
        object_id = split_entity_id(user_input["entity_id"])[1]
        entry = registry.async_get(user_input["entity_id"])
        if entry:
            return entry.name or entry.original_name or object_id
        state = self.hass.states.get(user_input["entity_id"])
        if state:
            return state.name or object_id
        return object_id
