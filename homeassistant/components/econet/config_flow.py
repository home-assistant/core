"""Config flow to configure the EcoNet component."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from pyeconet import EcoNetApiInterface
from pyeconet.errors import InvalidCredentialsError, PyeconetError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN

REAUTH_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class EcoNetFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an EcoNet config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data_schema = probatio.Schema(
            {
                probatio.Required(CONF_EMAIL): str,
                probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
            }
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
            )

        await self.async_set_unique_id(user_input[CONF_EMAIL])
        self._abort_if_unique_id_configured()
        errors = {}

        try:
            await EcoNetApiInterface.login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
        except InvalidCredentialsError:
            errors["base"] = "invalid_auth"
        except PyeconetError:
            errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
                errors=errors,
            )

        return self.async_create_entry(
            title=user_input[CONF_EMAIL],
            data={
                CONF_EMAIL: user_input[CONF_EMAIL],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        errors = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await EcoNetApiInterface.login(
                    reauth_entry.data[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except InvalidCredentialsError:
                errors["base"] = "invalid_auth"
            except PyeconetError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
            errors=errors,
        )
