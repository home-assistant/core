"""Config flow to configure the OVO Energy integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
from ovoenergy import OVOEnergy
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ACCOUNT, DOMAIN

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})
USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_ACCOUNT): str,
    }
)


class OVOEnergyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a OVO Energy config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self.username = None
        self.account = None

    async def async_step_user(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            client = OVOEnergy(
                client_session=async_get_clientsession(self.hass),
            )

            if (custom_account := user_input.get(CONF_ACCOUNT)) is not None:
                client.custom_account_id = custom_account

            try:
                authenticated = await client.authenticate(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                await client.bootstrap_accounts()
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            else:
                if authenticated:
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=client.username,
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_ACCOUNT: client.account_id,
                        },
                    )

                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        self.username = entry_data.get(CONF_USERNAME)
        self.account = entry_data.get(CONF_ACCOUNT)

        if self.username:
            # If we have a username, use it as flow title
            self.context["title_placeholders"] = {CONF_USERNAME: self.username}

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: Mapping[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        errors = {}

        if user_input is not None:
            client = OVOEnergy(
                client_session=async_get_clientsession(self.hass),
            )

            if self.account is not None:
                client.custom_account_id = self.account

            try:
                authenticated = await client.authenticate(
                    self.username,
                    user_input[CONF_PASSWORD],
                )
            except aiohttp.ClientError:
                errors["base"] = "connection_error"
            else:
                if authenticated:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(),
                        data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                    )

                errors["base"] = "authorization_error"

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )
