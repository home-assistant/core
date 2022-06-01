"""Config flow for Radio Thermostat integration."""
from __future__ import annotations

import logging
from socket import timeout
from typing import Any

import radiotherm
from radiotherm.thermostat import Thermostat
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


def _get_raw_data(tstat: Thermostat) -> dict[str, Any]:
    """Fetch the raw data from the thermostat."""
    return tstat.tstat["raw"]


async def validate_connection(hass: HomeAssistant, host: str) -> None:
    """Validate the connection"""
    tstat = radiotherm.get_thermostat(host)
    try:
        data = await hass.async_add_executor_job(_get_raw_data, tstat)
    except (timeout, radiotherm.validate.RadiothermTstatError):
        raise CannotConnect
    _LOGGER.warning("data: %s", data)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Radio Thermostat."""

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
            info = await validate_connection(self.hass, user_input[CONF_HOST])
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
