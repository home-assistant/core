"""Implement a config flow for anglian_water."""

from __future__ import annotations

from pyanglianwater import API
from pyanglianwater.exceptions import (
    InvalidPasswordError,
    InvalidUsernameError,
    ServiceUnavailableError,
    UnknownEndpointError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from .const import CONF_DEVICE_ID, DOMAIN

AW_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
        ),
        vol.Required(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
        ),
        vol.Optional(CONF_DEVICE_ID): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
        ),
    }
)


class AnglianWaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for anglian_water."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors: dict[str, str] = {}
        if user_input is not None:
            try:
                auth = await API.create_via_login(
                    email=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except (InvalidUsernameError, InvalidPasswordError):
                _errors["base"] = "invalid_auth"
            except ServiceUnavailableError:
                _errors["base"] = "maintenance"
            except UnknownEndpointError:
                _errors["base"] = "cannot_connect"
            else:
                user_input[CONF_DEVICE_ID] = auth.device_id
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                AW_DATA_SCHEMA, suggested_values=user_input
            ),
            errors=_errors,
        )
