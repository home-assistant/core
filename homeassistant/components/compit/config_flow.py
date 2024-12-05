"""Config flow for Compit integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from compit_inext_api import CompitAPI
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class CompitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Compit."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_create_clientsession(self.hass)
            api = CompitAPI(user_input[CONF_EMAIL], user_input[CONF_PASSWORD], session)
            try:
                success = await api.authenticate()
                if success and success.gates:
                    await self.async_set_unique_id(f"compit_{user_input[CONF_EMAIL]}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title="Compit", data=user_input)
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        reauth_entry_data = reauth_entry.data

        if user_input:
            session = async_create_clientsession(self.hass)

            api = CompitAPI(
                reauth_entry_data[CONF_EMAIL], user_input[CONF_PASSWORD], session
            )
            try:
                success = await api.authenticate()
                if success and success.gates:
                    return self.async_update_reload_and_abort(
                        reauth_entry, data_updates=user_input
                    )
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders={CONF_EMAIL: reauth_entry_data[CONF_EMAIL]},
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
