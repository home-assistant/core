"""Config flow for the Appwrite integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .appwrite import AppwriteClient, InvalidAuth, InvalidUrl
from .const import CONF_ENDPOINT, CONF_PROJECT_ID, CONF_TITLE, DOMAIN

STEP_APPWRITE_AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PROJECT_ID): str,
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate if the user input allows us to connect to Appwrite instance."""
    try:
        # Cannot use cv.url validation in the schema itself so apply
        # extra validation here
        cv.url(data[CONF_HOST])
    except vol.Invalid as vi:
        raise InvalidUrl from vi

    appwrite_client = AppwriteClient(data)
    if not await hass.async_add_executor_job(
        appwrite_client.async_validate_credentials
    ):
        raise InvalidAuth

    return {
        CONF_TITLE: f"{data[CONF_HOST]} - {data[CONF_PROJECT_ID]}",
        CONF_ENDPOINT: appwrite_client.endpoint,
        CONF_PROJECT_ID: appwrite_client.project_id,
        CONF_API_KEY: appwrite_client.api_key,
    }


class AppwriteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Appwrite."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = user_input[CONF_HOST].rstrip("/")
            self._async_abort_entries_match(
                {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_PROJECT_ID: user_input[CONF_PROJECT_ID],
                }
            )
            try:
                info = await validate_input(self.hass, user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except InvalidUrl:
                errors["base"] = "invalid_url"
            else:
                return self.async_create_entry(title=info[CONF_TITLE], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_APPWRITE_AUTH_SCHEMA, errors=errors
        )
