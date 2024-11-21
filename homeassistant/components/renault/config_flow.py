"""Config flow to configure Renault component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from renault_api.const import AVAILABLE_LOCALES
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_KAMEREON_ACCOUNT_ID, CONF_LOCALE, DOMAIN
from .renault_hub import RenaultHub

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

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Renault config flow."""
        self.renault_config: dict[str, Any] = {}
        self.renault_hub: RenaultHub | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a Renault config flow start.

        Ask the user for API keys.
        """
        if user_input:
            locale = user_input[CONF_LOCALE]
            self.renault_config.update(user_input)
            self.renault_config.update(AVAILABLE_LOCALES[locale])
            self.renault_hub = RenaultHub(self.hass, locale)
            if not await self.renault_hub.attempt_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            ):
                return self._show_user_form({"base": "invalid_credentials"})
            return await self.async_step_kamereon()
        return self._show_user_form()

    def _show_user_form(self, errors: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the API keys form."""
        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors or {},
        )

    async def async_step_kamereon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select Kamereon account."""
        if user_input:
            await self.async_set_unique_id(user_input[CONF_KAMEREON_ACCOUNT_ID])
            self._abort_if_unique_id_configured()

            self.renault_config.update(user_input)
            return self.async_create_entry(
                title=user_input[CONF_KAMEREON_ACCOUNT_ID], data=self.renault_config
            )

        assert self.renault_hub
        accounts = await self.renault_hub.get_account_ids()
        if len(accounts) == 0:
            return self.async_abort(reason="kamereon_no_account")
        if len(accounts) == 1:
            await self.async_set_unique_id(accounts[0])
            self._abort_if_unique_id_configured()

            self.renault_config[CONF_KAMEREON_ACCOUNT_ID] = accounts[0]
            return self.async_create_entry(
                title=self.renault_config[CONF_KAMEREON_ACCOUNT_ID],
                data=self.renault_config,
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
            errors=errors or {},
            description_placeholders={CONF_USERNAME: reauth_entry.data[CONF_USERNAME]},
        )
