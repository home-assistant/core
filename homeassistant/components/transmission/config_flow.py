"""Config flow for Transmission Bittorrent Client."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import callback

from . import get_api
from .const import (
    CONF_LIMIT,
    CONF_ORDER,
    DEFAULT_LIMIT,
    DEFAULT_NAME,
    DEFAULT_ORDER,
    DEFAULT_PATH,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DOMAIN,
    SUPPORTED_ORDER_MODES,
)
from .errors import AuthenticationError, CannotConnect, UnknownError

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PATH, default=DEFAULT_PATH): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class TransmissionFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Tansmission config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TransmissionOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TransmissionOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            try:
                await get_api(self.hass, user_input)

            except AuthenticationError:
                errors[CONF_USERNAME] = "invalid_auth"
                errors[CONF_PASSWORD] = "invalid_auth"
            except (CannotConnect, UnknownError):
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            user_input = {**reauth_entry.data, **user_input}
            try:
                await get_api(self.hass, user_input)

            except AuthenticationError:
                errors[CONF_PASSWORD] = "invalid_auth"
            except (CannotConnect, UnknownError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(reauth_entry, data=user_input)

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                CONF_NAME: reauth_entry.title,
            },
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class TransmissionOptionsFlowHandler(OptionsFlow):
    """Handle Transmission client options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Transmission options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Transmission options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_LIMIT,
                default=self.config_entry.options.get(CONF_LIMIT, DEFAULT_LIMIT),
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=500)),
            vol.Optional(
                CONF_ORDER,
                default=self.config_entry.options.get(CONF_ORDER, DEFAULT_ORDER),
            ): vol.All(vol.Coerce(str), vol.In(SUPPORTED_ORDER_MODES.keys())),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
