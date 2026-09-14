"""Config flow for the Vitesy integration."""

from collections.abc import Mapping
from typing import Any, override

from aiovitesy.api import VitesyApi
from aiovitesy.exceptions import CannotAuthenticate, VitesyError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def _validate_credentials(hass: HomeAssistant, email: str, password: str) -> None:
    """Try to authenticate, raising the aiovitesy error on failure."""
    api = VitesyApi(email, password, async_get_clientsession(hass))
    await api.login()


class VitesyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vitesy."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            try:
                await _validate_credentials(self.hass, email, user_input[CONF_PASSWORD])
            except CannotAuthenticate:
                errors["base"] = "invalid_auth"
            except VitesyError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=email, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication after a rejected token."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with an updated password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await _validate_credentials(
                    self.hass,
                    reauth_entry.data[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
            except CannotAuthenticate:
                errors["base"] = "invalid_auth"
            except VitesyError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
            errors=errors,
        )
