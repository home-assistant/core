"""Config flow for Transmission Bittorrent Client."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from transmission_rpc.error import (
    TransmissionAuthError,
    TransmissionConnectError,
    TransmissionError,
)

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
    MIN_REQUIRED_TRANSMISSION_VERSION,
    SUPPORTED_ORDER_MODES,
)
from .helpers import create_version

DATA_SCHEMA = probatio.Schema(
    {
        probatio.Optional(CONF_SSL, default=DEFAULT_SSL): bool,
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_PATH, default=DEFAULT_PATH): str,
        probatio.Optional(CONF_USERNAME): str,
        probatio.Optional(CONF_PASSWORD): str,
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class TransmissionFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle Transmission config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TransmissionOptionsFlowHandler:
        """Get the options flow for this handler."""
        return TransmissionOptionsFlowHandler()

    @override
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
                api = await get_api(self.hass, user_input)

            except TransmissionAuthError:
                errors[CONF_USERNAME] = "invalid_auth"
                errors[CONF_PASSWORD] = "invalid_auth"
            except TransmissionConnectError, TransmissionError:
                errors["base"] = "cannot_connect"
            else:
                version = create_version(api.server_version)
                if version.valid and version < MIN_REQUIRED_TRANSMISSION_VERSION:
                    errors["base"] = "transmission_version"

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
                api = await get_api(self.hass, user_input)

            except TransmissionAuthError:
                errors[CONF_PASSWORD] = "invalid_auth"
            except TransmissionConnectError, TransmissionError:
                errors["base"] = "cannot_connect"
            else:
                version = create_version(api.server_version)
                if version.valid and version < MIN_REQUIRED_TRANSMISSION_VERSION:
                    errors["base"] = "transmission_version"
                else:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data=user_input
                    )

        return self.async_show_form(
            description_placeholders={
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                CONF_NAME: reauth_entry.title,
            },
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class TransmissionOptionsFlowHandler(OptionsFlow):
    """Handle Transmission client options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Transmission options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            probatio.Optional(
                CONF_LIMIT,
                default=self.config_entry.options.get(CONF_LIMIT, DEFAULT_LIMIT),
            ): probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=500)),
            probatio.Optional(
                CONF_ORDER,
                default=self.config_entry.options.get(CONF_ORDER, DEFAULT_ORDER),
            ): probatio.All(
                probatio.Coerce(str), probatio.In(SUPPORTED_ORDER_MODES.keys())
            ),
        }

        return self.async_show_form(
            step_id="init", data_schema=probatio.Schema(options)
        )
