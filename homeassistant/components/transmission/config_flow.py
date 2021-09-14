"""Config flow for Transmission Bittorent Client."""
from __future__ import annotations

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
from homeassistant.helpers.typing import ConfigType

from .client import get_api
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
from .errors import AuthenticationError, TransmissionrBaseError

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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TransmissionOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TransmissionOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initiate config flow."""
        self._reauth_unique_id = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:

            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()

            try:
                await get_api(self.hass, user_input)

            except AuthenticationError:
                errors[CONF_USERNAME] = "invalid_auth"
                errors[CONF_PASSWORD] = "invalid_auth"
            except TransmissionrBaseError:
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

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import from Transmission client config."""
        import_config[CONF_SCAN_INTERVAL] = import_config[
            CONF_SCAN_INTERVAL
        ].total_seconds()
        return await self.async_step_user(user_input=import_config)

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_unique_id = self.context["unique_id"]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        existing_entry = await self.async_set_unique_id(self._reauth_unique_id)
        if user_input is not None and existing_entry is not None:
            user_input[CONF_HOST] = existing_entry.data[CONF_HOST]
            user_input[CONF_PORT] = existing_entry.data[CONF_PORT]
            try:
                await get_api(self.hass, user_input)

            except AuthenticationError:
                errors[CONF_USERNAME] = "invalid_auth"
                errors[CONF_PASSWORD] = "invalid_auth"
            except TransmissionrBaseError:
                errors["base"] = "cannot_connect"

            if not errors:
                self.hass.config_entries.async_update_entry(
                    existing_entry,
                    data={
                        **existing_entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                await self.hass.config_entries.async_reload(existing_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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
