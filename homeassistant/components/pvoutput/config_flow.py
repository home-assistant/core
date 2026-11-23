"""Config flow to configure the PVOutput integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from pvo import PVOutput, PVOutputAuthenticationError, PVOutputError, System

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SYSTEM_ID, DOMAIN, LOGGER


async def validate_input(
    hass: HomeAssistant, *, api_key: str, system_id: int
) -> System:
    """Try using the given system ID and API key against the PVOutput API."""
    session = async_get_clientsession(hass)
    pvoutput = PVOutput(
        session=session,
        api_key=api_key,
        system_id=system_id,
    )
    return await pvoutput.system()


class PVOutputFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for PVOutput."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            try:
                system = await validate_input(
                    self.hass,
                    api_key=user_input[CONF_API_KEY],
                    system_id=user_input[CONF_SYSTEM_ID],
                )
            except PVOutputAuthenticationError:
                errors["base"] = "invalid_auth"
            except PVOutputError:
                LOGGER.exception("Cannot connect to PVOutput")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(user_input[CONF_SYSTEM_ID]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=system.system_name,
                    data={
                        CONF_SYSTEM_ID: user_input[CONF_SYSTEM_ID],
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "account_url": "https://pvoutput.org/account.jsp"
            },
            data_schema=self.add_suggested_values_to_schema(
                probatio.Schema(
                    {
                        probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                        probatio.Required(CONF_SYSTEM_ID): int,
                    }
                ),
                user_input,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of a PVOutput entry."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                await validate_input(
                    self.hass,
                    api_key=user_input[CONF_API_KEY],
                    system_id=reconfigure_entry.data[CONF_SYSTEM_ID],
                )
            except PVOutputAuthenticationError:
                errors["base"] = "invalid_auth"
            except PVOutputError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            description_placeholders={
                "account_url": "https://pvoutput.org/account.jsp"
            },
            data_schema=probatio.Schema(
                {
                    probatio.Required(probatio.Secret(CONF_API_KEY)): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with PVOutput."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with PVOutput."""
        errors = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            try:
                await validate_input(
                    self.hass,
                    api_key=user_input[CONF_API_KEY],
                    system_id=reauth_entry.data[CONF_SYSTEM_ID],
                )
            except PVOutputAuthenticationError:
                errors["base"] = "invalid_auth"
            except PVOutputError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={
                "account_url": "https://pvoutput.org/account.jsp"
            },
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_API_KEY)): str}
            ),
            errors=errors,
        )
