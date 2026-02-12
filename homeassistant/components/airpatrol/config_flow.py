"""Config flow for the AirPatrol integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from airpatrol.api import AirPatrolAPI, AirPatrolAuthenticationError, AirPatrolError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="email",
            )
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


async def validate_api(
    hass: HomeAssistant, user_input: dict[str, str]
) -> tuple[str | None, str | None, dict[str, str]]:
    """Validate the API connection."""
    errors: dict[str, str] = {}
    session = async_get_clientsession(hass)
    access_token = None
    unique_id = None
    try:
        api = await AirPatrolAPI.authenticate(
            session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
        )
    except AirPatrolAuthenticationError:
        errors["base"] = "invalid_auth"
    except AirPatrolError:
        errors["base"] = "cannot_connect"
    else:
        access_token = api.get_access_token()
        unique_id = api.get_unique_id()

    return (access_token, unique_id, errors)


class AirPatrolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirPatrol."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            access_token, unique_id, errors = await validate_api(self.hass, user_input)
            if access_token and unique_id:
                user_input[CONF_ACCESS_TOKEN] = access_token
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication with new credentials."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthentication confirmation."""
        errors: dict[str, str] = {}

        if user_input:
            access_token, unique_id, errors = await validate_api(self.hass, user_input)
            if access_token and unique_id:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_mismatch()
                user_input[CONF_ACCESS_TOKEN] = access_token
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=DATA_SCHEMA, errors=errors
        )
