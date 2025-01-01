"""Config flow for igloohome integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientError
from igloohome_api import Auth as IgloohomeAuth, AuthException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
    }
)


class IgloohomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for igloohome."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the config flow step."""

        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_CLIENT_ID: user_input[CONF_CLIENT_ID],
                }
            )
            auth = IgloohomeAuth(
                session=async_get_clientsession(self.hass),
                client_id=user_input[CONF_CLIENT_ID],
                client_secret=user_input[CONF_CLIENT_SECRET],
            )
            try:
                await auth.async_get_access_token()
            except AuthException:
                errors["base"] = "invalid_auth"
            except ClientError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Client Credentials", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
