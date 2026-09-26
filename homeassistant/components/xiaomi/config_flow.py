"""Config flow for the Xiaomi integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import DEFAULT_USERNAME, DOMAIN
from .router import (
    XiaomiAuthError,
    XiaomiClient,
    XiaomiConnectionError,
    XiaomiTimeoutError,
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(CONF_PASSWORD): str,
    }
)


class XiaomiConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Xiaomi."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}

        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

        try:
            await self._async_validate(user_input)
        except XiaomiAuthError:
            errors["base"] = "invalid_auth"
        except XiaomiTimeoutError, XiaomiConnectionError:
            errors["base"] = "cannot_connect"
        else:
            return self.async_create_entry(
                title=user_input[CONF_HOST],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        reauth_entry = self._get_reauth_entry()

        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_DATA_SCHEMA,
                description_placeholders={"host": reauth_entry.data[CONF_HOST]},
            )

        errors: dict[str, str] = {}

        try:
            await self._async_validate(reauth_entry.data | user_input)
        except XiaomiAuthError:
            errors["base"] = "invalid_auth"
        except XiaomiTimeoutError, XiaomiConnectionError:
            errors["base"] = "cannot_connect"
        else:
            return self.async_update_reload_and_abort(
                reauth_entry, data_updates=user_input
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"host": reauth_entry.data[CONF_HOST]},
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from legacy YAML configuration."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})

        try:
            await self._async_validate(import_data)
        except XiaomiAuthError:
            return self.async_abort(reason="invalid_auth")
        except XiaomiTimeoutError, XiaomiConnectionError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(
            title=import_data[CONF_HOST],
            data=import_data,
        )

    async def _async_validate(self, user_input: dict[str, Any]) -> None:
        """Log in to the router to validate the given configuration."""
        client = XiaomiClient(
            user_input[CONF_HOST],
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
        )
        await self.hass.async_add_executor_job(client.login)
