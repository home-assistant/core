"""Config flow for Nee-Vo Tank Monitoring integration."""

from __future__ import annotations

import logging

from pyneevo import NeeVoApiInterface
from pyneevo.errors import InvalidCredentialsError, PyNeeVoError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Nee-Vo config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data_schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
            )

        await self.async_set_unique_id(user_input[CONF_EMAIL])
        self._abort_if_unique_id_configured()
        errors = {}

        try:
            await NeeVoApiInterface.login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
        except InvalidCredentialsError:
            errors["base"] = "invalid_auth"
        except PyNeeVoError:
            errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
                errors=errors,
            )

        return self.async_create_entry(
            title=user_input[CONF_EMAIL],
            data={
                CONF_EMAIL: user_input[CONF_EMAIL],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            },
        )
