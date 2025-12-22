"""config flow for Imou."""

from __future__ import annotations

import logging
from typing import Any

from pyimouapi.exceptions import ImouException
from pyimouapi.openapi import ImouOpenApiClient
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_API_URL_FK,
    CONF_API_URL_HZ,
    CONF_API_URL_OR,
    CONF_API_URL_SG,
    DOMAIN,
    PARAM_API_URL,
    PARAM_APP_ID,
    PARAM_APP_SECRET,
    PARAM_ROTATION_DURATION,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)

VERSION = 1
MINOR_VERSION = 1


class ImouConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Imou integration."""

    VERSION = VERSION
    MINOR_VERSION = MINOR_VERSION

    @staticmethod
    def _get_login_schema() -> vol.Schema:
        """Get the login schema.

        Returns:
            Voluptuous schema for login form
        """
        return vol.Schema(
            {
                vol.Required(PARAM_APP_ID): str,
                vol.Required(PARAM_APP_SECRET): str,
                vol.Required(PARAM_API_URL, default=CONF_API_URL_SG): vol.In(
                    [
                        CONF_API_URL_SG,
                        CONF_API_URL_OR,
                        CONF_API_URL_FK,
                        CONF_API_URL_HZ,
                    ]
                ),
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow.

        Args:
            user_input: User input dictionary, None if first step

        Returns:
            Config flow result
        """
        # Show form if user input is empty.
        if user_input is None:
            return self.async_show_form(
                step_id="login",
                data_schema=self._get_login_schema(),
            )
        # Start login if user input is provided.
        return await self.async_step_login(user_input)

    async def async_step_login(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Handle the login step of the config flow.

        Args:
            user_input: User input dictionary containing app_id, app_secret, and api_url

        Returns:
            Config flow result

        Raises:
            ImouException: If authentication fails
        """
        await self.async_set_unique_id(user_input[PARAM_APP_ID])
        self._abort_if_unique_id_configured()
        api_client = ImouOpenApiClient(
            user_input[PARAM_APP_ID],
            user_input[PARAM_APP_SECRET],
            user_input[PARAM_API_URL],
        )
        errors = {}
        try:
            await api_client.async_get_token()
            data = {
                PARAM_APP_ID: user_input[PARAM_APP_ID],
                PARAM_APP_SECRET: user_input[PARAM_APP_SECRET],
                PARAM_API_URL: user_input[PARAM_API_URL],
            }
            return self.async_create_entry(title=DOMAIN, data=data)
        except ImouException as exception:
            errors["base"] = exception.get_title()
            return self.async_show_form(
                step_id="login",
                data_schema=self._get_login_schema(),
                errors=errors,
            )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler.

        Args:
            config_entry: Configuration entry

        Returns:
            Options flow instance
        """
        return ImouOptionsFlow()


class ImouOptionsFlow(OptionsFlow):
    """Handle an options flow for Imou."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options flow.

        Args:
            user_input: User input dictionary, None if first step

        Returns:
            Config flow result
        """
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(PARAM_ROTATION_DURATION, default=500): vol.All(
                            vol.Coerce(int), vol.Range(min=100, max=10000)
                        ),
                    }
                ),
                self.config_entry.options,
            ),
        )
