"""Config flow for the Hitron CODA integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TYPE, CONF_USERNAME

from .api import CannotConnect, HitronCodaClient, InvalidAuth
from .const import DEFAULT_TYPE, DOMAIN, ROUTER_TYPES

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): str,
        probatio.Required(CONF_USERNAME): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
        probatio.Optional(CONF_TYPE, default=DEFAULT_TYPE): probatio.In(ROUTER_TYPES),
    }
)


class HitronCodaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle setup and credential changes for the router."""

    VERSION = 1

    async def _async_validate_input(self, data: Mapping[str, Any]) -> None:
        """Validate credentials using the same device request as polling."""
        client = HitronCodaClient(
            data[CONF_HOST],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data.get(CONF_TYPE, DEFAULT_TYPE),
        )
        await self.hass.async_add_executor_job(client.get_devices)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            try:
                await self._async_validate_input(user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception setting up Hitron CODA")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Import credentials from the legacy device tracker platform."""
        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        try:
            await self._async_validate_input(user_input)
        except InvalidAuth:
            return self.async_abort(reason="invalid_auth")
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication for an existing router."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate replacement credentials before reloading the entry."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._async_validate_input({**entry.data, **user_input})
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_USERNAME, default=entry.data[CONF_USERNAME]
                    ): str,
                    probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )
