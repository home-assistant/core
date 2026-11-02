"""Config flow for the Vitesy integration."""

from collections.abc import Mapping
from typing import Any, override

from aiovitesy.api import VitesyApi
from aiovitesy.exceptions import CannotAuthenticate, VitesyError
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="username",
            )
        ),
        probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD_SELECTOR,
    }
)

STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD_SELECTOR,
    }
)


async def _validate_credentials(hass: HomeAssistant, email: str, password: str) -> str:
    """Authenticate and return the account's stable user id."""
    api = VitesyApi(email, password, async_get_clientsession(hass))
    await api.login()
    user = await api.get_user()
    user_id = user.get("id")
    if not isinstance(user_id, (str, int)):
        raise VitesyError(f"Profile response is missing a valid user id: {user_id!r}")
    return str(user_id)


class VitesyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vitesy."""

    async def _async_validate_input(
        self, email: str, password: str, errors: dict[str, str]
    ) -> str | None:
        """Validate the credentials, return the user id or record an error."""
        try:
            return await _validate_credentials(self.hass, email, password)
        except CannotAuthenticate:
            errors["base"] = "invalid_auth"
        except VitesyError:
            errors["base"] = "cannot_connect"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]
            user_id = await self._async_validate_input(
                email, user_input[CONF_PASSWORD], errors
            )
            if user_id is not None:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=email, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the stored credentials are rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password for the existing account."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        email = reauth_entry.data[CONF_EMAIL]
        if user_input is not None:
            user_id = await self._async_validate_input(
                email, user_input[CONF_PASSWORD], errors
            )
            if user_id is not None:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={CONF_EMAIL: email},
            errors=errors,
        )
