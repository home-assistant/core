"""Config flow for Aladdin Connect cover integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from AIOAladdinConnect import AladdinConnectClient
import AIOAladdinConnect.session_manager as Aladdin
from aiohttp.client_exceptions import ClientError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CLIENT_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    acc = AladdinConnectClient(
        data[CONF_USERNAME],
        data[CONF_PASSWORD],
        async_get_clientsession(hass),
        CLIENT_ID,
    )
    try:
        await acc.login()
    except (ClientError, asyncio.TimeoutError, Aladdin.ConnectionError) as ex:
        raise ex

    except Aladdin.InvalidPasswordError as ex:
        raise InvalidAuth from ex


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Aladdin Connect."""

    VERSION = 1
    entry: config_entries.ConfigEntry | None

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle re-authentication with Aladdin Connect."""

        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm re-authentication with Aladdin Connect."""
        errors: dict[str, str] = {}

        if user_input:
            assert self.entry is not None
            password = user_input[CONF_PASSWORD]
            data = {
                CONF_USERNAME: self.entry.data[CONF_USERNAME],
                CONF_PASSWORD: password,
            }

            try:
                await validate_input(self.hass, data)

            except InvalidAuth:
                errors["base"] = "invalid_auth"

            except (ClientError, asyncio.TimeoutError, Aladdin.ConnectionError):
                errors["base"] = "cannot_connect"

            else:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    data={
                        **self.entry.data,
                        CONF_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await validate_input(self.hass, user_input)
        except InvalidAuth:
            errors["base"] = "invalid_auth"

        except (ClientError, asyncio.TimeoutError, Aladdin.ConnectionError):
            errors["base"] = "cannot_connect"

        else:
            await self.async_set_unique_id(
                user_input["username"].lower(), raise_on_progress=False
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Aladdin Connect", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Import Aladin Connect config from configuration.yaml."""
        return await self.async_step_user(import_data)


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
