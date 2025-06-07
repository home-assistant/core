"""Config flow to configure Renault component."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
from renault_api.const import AVAILABLE_LOCALES
from renault_api.gigya.exceptions import GigyaException
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_KAMEREON_ACCOUNT_ID, CONF_LOCALE, DOMAIN
from .renault_hub import RenaultHub

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LOCALE): vol.In(AVAILABLE_LOCALES.keys()),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class RenaultFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Renault config flow."""

    renault_hub: RenaultHub

    def __init__(self) -> None:
        """Initialize the Renault config flow."""
        self.renault_config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a Renault config flow start.

        Ask the user for API keys.
        """
        errors: dict[str, str] = {}
        suggested_values: Mapping[str, Any] | None = None
        if user_input:
            locale = user_input[CONF_LOCALE]
            self.renault_config.update(user_input)
            self.renault_config.update(AVAILABLE_LOCALES[locale])
            self.renault_hub = RenaultHub(self.hass, locale)
            try:
                login_success = await self.renault_hub.attempt_login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except (aiohttp.ClientConnectionError, GigyaException):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if login_success:
                    return await self.async_step_kamereon()
                errors["base"] = "invalid_credentials"
            suggested_values = user_input
        elif self.source == SOURCE_RECONFIGURE:
            suggested_values = self._get_reconfigure_entry().data

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA, suggested_values
            ),
            errors=errors,
        )

    async def async_step_kamereon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Kamereon account."""
        if user_input:
            await self.async_set_unique_id(user_input[CONF_KAMEREON_ACCOUNT_ID])
            if self.source == SOURCE_RECONFIGURE:
                self._abort_if_unique_id_mismatch()
                self.renault_config.update(user_input)
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates=self.renault_config,
                )

            self._abort_if_unique_id_configured()

            self.renault_config.update(user_input)
            return self.async_create_entry(
                title=user_input[CONF_KAMEREON_ACCOUNT_ID], data=self.renault_config
            )

        accounts = await self.renault_hub.get_account_ids()
        if len(accounts) == 0:
            return self.async_abort(reason="kamereon_no_account")
        if len(accounts) == 1:
            return await self.async_step_kamereon(
                user_input={CONF_KAMEREON_ACCOUNT_ID: accounts[0]}
            )

        return self.async_show_form(
            step_id="kamereon",
            data_schema=vol.Schema(
                {vol.Required(CONF_KAMEREON_ACCOUNT_ID): vol.In(accounts)}
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input:
            # Check credentials
            self.renault_hub = RenaultHub(self.hass, reauth_entry.data[CONF_LOCALE])
            if await self.renault_hub.attempt_login(
                reauth_entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
            ):
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
            errors = {"base": "invalid_credentials"}

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={CONF_USERNAME: reauth_entry.data[CONF_USERNAME]},
        )

    async def async_step_reconfigure(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        return await self.async_step_user()
