"""Xonfig flow for Imou."""
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    DOMAIN, PARAM_API_URL, PARAM_APP_ID, PARAM_APP_SECRET, CONF_API_URL_OR, CONF_API_URL_FK,
    CONF_API_URL_SG,
)
from pyimouapi.exceptions import ImouException
from pyimouapi.openapi import ImouOpenApiClient

_LOGGER: logging.Logger = logging.getLogger(__package__)


class ImouConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    def __init__(self):
        self._api_url = None
        self._app_id = None
        self._app_secret = None
        self._api_client = None
        self._session = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        # USER INPUT IS EMPTY RETURN TO FORM
        if user_input is None:
            return self.async_show_form(
                step_id="login",
                data_schema=vol.Schema(
                    {
                        vol.Required(PARAM_APP_ID): str,
                        vol.Required(PARAM_APP_SECRET): str,
                        vol.Required(PARAM_API_URL, default=CONF_API_URL_SG): vol.In(
                            [ CONF_API_URL_SG, CONF_API_URL_OR, CONF_API_URL_FK]
                        ),
                    }
                )
            )
        # USER INPUT IS NOT EMPTY START LOGIN
        return await self.async_step_login(user_input)

    async def async_step_login(self, user_input):
        await self.async_set_unique_id(user_input[PARAM_APP_ID])
        self._abort_if_unique_id_configured()
        api_client = ImouOpenApiClient(user_input[PARAM_APP_ID], user_input[PARAM_APP_SECRET], user_input[PARAM_API_URL])
        errors = {}
        try:
            await api_client.async_get_token()
            data = {
                PARAM_APP_ID: user_input[PARAM_APP_ID],
                PARAM_APP_SECRET: user_input[PARAM_APP_SECRET],
                PARAM_API_URL: user_input[PARAM_API_URL],
            }
            return self.async_create_entry(
                title=DOMAIN,
                data=data
            )
        except ImouException as exception:
            errors["base"] = exception.get_title()
            return self.async_show_form(
                step_id="login",
                data_schema=vol.Schema(
                    {
                        vol.Required(PARAM_APP_ID): str,
                        vol.Required(PARAM_APP_SECRET): str,
                        vol.Required(PARAM_API_URL, default=CONF_API_URL_SG): vol.In(
                            [CONF_API_URL_SG, CONF_API_URL_OR, CONF_API_URL_FK]
                        ),
                    }
                ),
                errors=errors
            )