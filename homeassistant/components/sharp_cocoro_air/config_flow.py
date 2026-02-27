"""Config flow for Sharp COCORO Air integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiosharp_cocoro_air import SharpAuthError, SharpCOCOROAir, SharpConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SharpCocoroAirConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sharp COCORO Air."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step -- email/password entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                async with SharpCOCOROAir(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                ) as client:
                    await client.authenticate()
            except SharpAuthError:
                errors["base"] = "invalid_auth"
            except SharpConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Sharp login")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Sharp COCORO Air ({user_input[CONF_EMAIL]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],
    ) -> ConfigFlowResult:
        """Handle reauth when session/credentials expire."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reauth confirmation with new credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                async with SharpCOCOROAir(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                ) as client:
                    await client.authenticate()
            except SharpAuthError:
                errors["base"] = "invalid_auth"
            except SharpConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Sharp reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates=user_input,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
