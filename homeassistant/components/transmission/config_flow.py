"""Config flow for Transmission Bittorent Client."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from . import get_api
from .const import (
    CONF_LIMIT,
    CONF_ORDER,
    DEFAULT_LIMIT,
    DEFAULT_NAME,
    DEFAULT_ORDER,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SUPPORTED_ORDER_MODES,
)
from .errors import AuthenticationError, CannotConnect, UnknownError

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class TransmissionFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Tansmission config flow."""

    VERSION = 1
    _reauth_entry: config_entries.ConfigEntry | None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TransmissionOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TransmissionOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            for entry in self._async_current_entries():
                if (
                    entry.data[CONF_HOST] == user_input[CONF_HOST]
                    and entry.data[CONF_PORT] == user_input[CONF_PORT]
                ):
                    return self.async_abort(reason="already_configured")
                if entry.data[CONF_NAME] == user_input[CONF_NAME]:
                    errors[CONF_NAME] = "name_exists"
                    break
            try:
                await get_api(self.hass, user_input)

            except AuthenticationError:
                errors[CONF_USERNAME] = "invalid_auth"
                errors[CONF_PASSWORD] = "invalid_auth"
            except (CannotConnect, UnknownError):
                errors["base"] = "cannot_connect"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors = {}
        assert self._reauth_entry
        if user_input is not None:
            user_input = {**self._reauth_entry.data, **user_input}
            try:
                await get_api(self.hass, user_input)

            except AuthenticationError:
                errors[CONF_PASSWORD] = "invalid_auth"
            except (CannotConnect, UnknownError):
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: self._reauth_entry.data[CONF_USERNAME]
            },
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class TransmissionOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Transmission client options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize Transmission options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Transmission options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
            ): int,
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
