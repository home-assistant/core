"""Config flow for Imou."""

from __future__ import annotations

from typing import Any

from pyimouapi.exceptions import ImouException
from pyimouapi.openapi import ImouOpenApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import API_URLS, CONF_API_URL, CONF_APP_ID, CONF_APP_SECRET, DOMAIN


class ImouConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Imou integration."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the config flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_APP_ID])
            self._abort_if_unique_id_configured()
            api_client = ImouOpenApiClient(
                user_input[CONF_APP_ID],
                user_input[CONF_APP_SECRET],
                API_URLS[user_input[CONF_API_URL]],
            )
            try:
                await api_client.async_get_token()
            except ImouException as exception:
                errors["base"] = exception.get_title()
            else:
                return self.async_create_entry(
                    title=DOMAIN,
                    data={
                        CONF_APP_ID: user_input[CONF_APP_ID],
                        CONF_APP_SECRET: user_input[CONF_APP_SECRET],
                        CONF_API_URL: user_input[CONF_API_URL],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APP_ID): str,
                    vol.Required(CONF_APP_SECRET): str,
                    vol.Required(CONF_API_URL, default="sg"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=key, label=key)
                                for key in API_URLS
                            ],
                            translation_key="api_url",
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )
