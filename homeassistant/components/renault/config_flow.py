"""Config flow to configure Renault component."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from renault_api.const import AVAILABLE_LOCALES
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_KAMEREON_ACCOUNT_ID, CONF_LOCALE, DOMAIN
from .renault_hub import RenaultHub


class RenaultFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Renault config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Renault config flow."""
        self._original_data: dict[str, Any] | None = None
        self.renault_config: dict[str, Any] = {}
        self.renault_hub: RenaultHub | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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

    def _show_user_form(self, errors: dict[str, Any] | None = None) -> FlowResult:
        """Show the API keys form."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCALE): vol.In(AVAILABLE_LOCALES.keys()),
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_kamereon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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

    async def async_step_reauth(self, user_input: dict[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._original_data = user_input.copy()
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if not user_input:
            return self._show_reauth_confirm_form()

        if TYPE_CHECKING:
            assert self._original_data

        # Check credentials
        self.renault_hub = RenaultHub(self.hass, self._original_data[CONF_LOCALE])
        if not await self.renault_hub.attempt_login(
            self._original_data[CONF_USERNAME], user_input[CONF_PASSWORD]
        ):
            return self._show_reauth_confirm_form({"base": "invalid_credentials"})

        # Update existing entry
        data = {**self._original_data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
        existing_entry = await self.async_set_unique_id(
            self._original_data[CONF_KAMEREON_ACCOUNT_ID]
        )
        if TYPE_CHECKING:
            assert existing_entry
        self.hass.config_entries.async_update_entry(existing_entry, data=data)
        await self.hass.config_entries.async_reload(existing_entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    def _show_reauth_confirm_form(
        self, errors: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the API keys form."""
        if TYPE_CHECKING:
            assert self._original_data
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors or {},
            description_placeholders={
                CONF_USERNAME: self._original_data[CONF_USERNAME]
            },
        )
