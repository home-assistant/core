"""Config flow for Waterkotte Heatpump integration."""
from __future__ import annotations

import logging
from typing import Any

from pywaterkotte import (
    AuthenticationException,
    ConnectionException,
    Ecotouch,
    EcotouchTags,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Required("username", default="waterkotte"): str,
        vol.Required("password", default="waterkotte"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    def get_heatpump() -> Ecotouch:
        heatpump = Ecotouch(data["host"])
        heatpump.login(data["username"], data["password"])
        return heatpump

    try:
        heatpump = await hass.async_add_executor_job(get_heatpump)
        hp_type = await hass.async_add_executor_job(
            heatpump.read_value, EcotouchTags.HEATPUMP_TYPE
        )

        series = await hass.async_add_executor_job(
            heatpump.decode_heatpump_series, hp_type
        )
        # Return info that you want to store in the config entry.
        return {"title": f"{series}"}

    except ConnectionException as exc:
        raise CannotConnect(ConnectionException) from exc
    except AuthenticationException as status_exception:
        raise InvalidAuth(status_exception) from status_exception


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Waterkotte Heatpump."""

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
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
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


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
