"""Config flow for Powerfox integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from powerfox import Powerfox, PowerfoxAuthenticationError, PowerfoxConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class PowerfoxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Powerfox."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})
            client = Powerfox(
                username=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await client.all_devices()
            except PowerfoxAuthenticationError:
                errors["base"] = "invalid_auth"
            except PowerfoxConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=STEP_USER_DATA_SCHEMA,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication flow for Powerfox."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication flow for Powerfox."""
        errors = {}

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            client = Powerfox(
                username=reauth_entry.data[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await client.all_devices()
            except PowerfoxAuthenticationError:
                errors["base"] = "invalid_auth"
            except PowerfoxConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"email": reauth_entry.data[CONF_EMAIL]},
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure Powerfox configuration."""
        errors = {}

        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None:
            client = Powerfox(
                username=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await client.all_devices()
            except PowerfoxAuthenticationError:
                errors["base"] = "invalid_auth"
            except PowerfoxConnectionError:
                errors["base"] = "cannot_connect"
            else:
                if reconfigure_entry.data[CONF_EMAIL] != user_input[CONF_EMAIL]:
                    self._async_abort_entries_match(
                        {CONF_EMAIL: user_input[CONF_EMAIL]}
                    )
                return self.async_update_reload_and_abort(
                    reconfigure_entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
