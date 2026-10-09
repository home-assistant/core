"""Config flow for FortiOS."""

from collections.abc import Mapping
from typing import Any, override

from aiofortiosapi import FortiOSAuthenticationError, FortiOSError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResultType

from .client import FortiOSClient, UnsupportedVersion
from .const import DOMAIN


class FortiOSConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure FortiOS using its API token."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                client = FortiOSClient(self.hass, user_input)
                serial = await client.connect()
            except FortiOSAuthenticationError:
                errors["base"] = "invalid_auth"
            except FortiOSError:
                errors["base"] = "cannot_connect"
            except UnsupportedVersion:
                errors["base"] = "unsupported_version"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_HOST): str,
                    probatio.Required(probatio.Secret(CONF_TOKEN)): str,
                    probatio.Optional(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import legacy YAML without duplicating existing entries."""
        self._async_abort_entries_match({CONF_HOST: import_data[CONF_HOST]})
        result = await self.async_step_user(import_data)
        if result["type"] is FlowResultType.FORM:
            errors = result["errors"]
            assert errors is not None
            return self.async_abort(reason=errors["base"])
        return result

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Request a replacement API token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate the replacement token against the same device."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                client = FortiOSClient(self.hass, dict(entry.data) | user_input)
                serial = await client.connect()
            except FortiOSAuthenticationError:
                errors["base"] = "invalid_auth"
            except FortiOSError:
                errors["base"] = "cannot_connect"
            except UnsupportedVersion:
                errors["base"] = "unsupported_version"
            else:
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_TOKEN)): str}
            ),
            errors=errors,
        )
