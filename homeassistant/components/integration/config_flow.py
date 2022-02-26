"""Config flow for Integration integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_METHOD, TIME_HOURS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ROUND_DIGITS,
    CONF_SOURCE_SENSOR,
    CONF_UNIT_PREFIX,
    CONF_UNIT_TIME,
    DEFAULT_ROUND,
    DOMAIN,
    INTEGRATION_METHOD,
    TRAPEZOIDAL_METHOD,
    UNIT_PREFIXES,
    UNIT_TIME,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_SENSOR): cv.string,
        vol.Required(CONF_ROUND_DIGITS, default=DEFAULT_ROUND): vol.Coerce(int),
        vol.Optional(CONF_UNIT_PREFIX): vol.In(UNIT_PREFIXES.keys()),
        vol.Required(CONF_UNIT_TIME, default=TIME_HOURS): vol.In(UNIT_TIME.keys()),
        vol.Required(CONF_METHOD, default=TRAPEZOIDAL_METHOD): vol.In(
            INTEGRATION_METHOD
        ),
    }
)


async def validate_input(data: dict[str, Any], hass: HomeAssistant) -> None:
    """Validate the user input allows us to connect."""

    if hass.states.get(data[CONF_SOURCE_SENSOR]) is None:
        raise InvalidSourceSensorError


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(user_input, self.hass)
        except InvalidSourceSensorError:
            errors["base"] = "invalid_source"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            self._async_abort_entries_match(user_input)

            return self.async_create_entry(
                title=f"{user_input[CONF_SOURCE_SENSOR]} integral", data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class InvalidSourceSensorError(Exception):
    """Handle invalid entity ids."""
