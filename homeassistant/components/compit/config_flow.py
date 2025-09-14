"""Config flow for Compit integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from compit_inext_api import CannotConnect, CompitApiConnector, InvalidAuth
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): str,
    }
)


class CompitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Compit."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_create_clientsession(self.hass)
            api = CompitApiConnector(session)
            success = False
            try:
                success = await api.init(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    self.hass.config.language,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if success:
                await self.async_set_unique_id(user_input[CONF_EMAIL])

                if self.source == SOURCE_REAUTH:
                    self._abort_if_unique_id_mismatch()
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data_updates=user_input
                    )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

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
            # Reuse async_step_user with combined credentials
            return await self.async_step_user(
                {
                    CONF_EMAIL: reauth_entry_data[CONF_EMAIL],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                }
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            description_placeholders={CONF_EMAIL: reauth_entry_data[CONF_EMAIL]},
            errors=errors,
        )
