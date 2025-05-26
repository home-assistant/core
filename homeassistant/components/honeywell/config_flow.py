"""Config flow to configure the honeywell integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiosomecomfort
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_HEAT_AWAY_TEMPERATURE,
    DEFAULT_COOL_AWAY_TEMPERATURE,
    DEFAULT_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HoneywellConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a honeywell config flow."""

    VERSION = 1

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with Honeywell."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with Honeywell."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        if user_input:
            try:
                await self.is_valid(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )

            except aiosomecomfort.AuthError:
                errors["base"] = "invalid_auth"
            except (
                aiosomecomfort.ConnectionError,
                aiosomecomfort.ConnectionTimeout,
                TimeoutError,
            ):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, reauth_entry.data
            ),
            errors=errors,
            description_placeholders={"name": "Honeywell"},
        )

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Create config entry. Show the setup form to the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self.is_valid(**user_input)
            except aiosomecomfort.AuthError:
                errors["base"] = "invalid_auth"
            except (
                aiosomecomfort.ConnectionError,
                aiosomecomfort.ConnectionTimeout,
                TimeoutError,
            ):
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(
                    title=DOMAIN,
                    data=user_input,
                )

        data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    async def is_valid(self, **kwargs) -> bool:
        """Check if login credentials are valid."""
        client = aiosomecomfort.AIOSomeComfort(
            kwargs[CONF_USERNAME],
            kwargs[CONF_PASSWORD],
            session=async_get_clientsession(self.hass),
        )

        await client.login()
        return True

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HoneywellOptionsFlowHandler:
        """Options callback for Honeywell."""
        return HoneywellOptionsFlowHandler()


class HoneywellOptionsFlowHandler(OptionsFlow):
    """Config flow options for Honeywell."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title=DOMAIN, data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COOL_AWAY_TEMPERATURE,
                        default=self.config_entry.options.get(
                            CONF_COOL_AWAY_TEMPERATURE, DEFAULT_COOL_AWAY_TEMPERATURE
                        ),
                    ): int,
                    vol.Required(
                        CONF_HEAT_AWAY_TEMPERATURE,
                        default=self.config_entry.options.get(
                            CONF_HEAT_AWAY_TEMPERATURE, DEFAULT_HEAT_AWAY_TEMPERATURE
                        ),
                    ): int,
                }
            ),
        )
