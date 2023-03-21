"""Config flow for Livisi Home Assistant."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress
from typing import Any

from aiohttp import ClientConnectorError
from aiolivisi import AioLivisi, errors as livisi_errors
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import CONF_HOST, CONF_PASSWORD, DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class LivisiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Livisi Smart Home config flow."""

    reauth_entry: config_entries.ConfigEntry | None = None

    def __init__(self) -> None:
        """Create the configuration file."""

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
        errors = {}
        try:
            aio_livisi = await self._login(user_input)
        except livisi_errors.WrongCredentialException:
            errors["base"] = "wrong_password"
        except livisi_errors.ShcUnreachableException:
            errors["base"] = "cannot_connect"
        except livisi_errors.IncorrectIpAddressException:
            errors["base"] = "wrong_ip_address"
        else:
            controller_info: dict[str, Any] = {}
            with suppress(ClientConnectorError):
                controller_info = await aio_livisi.async_get_controller()
            if controller_info:
                return await self.create_or_update_entry(user_input, controller_info)
            errors["base"] = "cannot_connect"

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input)
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input:
            return await self.async_step_user(user_input)
        assert self.reauth_entry
        data_schema = self.add_suggested_values_to_schema(
            DATA_SCHEMA, self.reauth_entry.data
        )
        return self.async_show_form(step_id="reauth_confirm", data_schema=data_schema)

    async def _login(self, user_input: dict[str, str]) -> AioLivisi:
        """Login into Livisi Smart Home."""
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        aio_livisi = AioLivisi(web_session)
        livisi_connection_data = {
            "ip_address": user_input[CONF_HOST],
            "password": user_input[CONF_PASSWORD],
        }

        await aio_livisi.async_set_token(livisi_connection_data)
        return aio_livisi

    async def create_or_update_entry(
        self, user_input: dict[str, str], controller_info: dict[str, Any]
    ) -> FlowResult:
        """Create LIVISI entity."""
        if self.reauth_entry:
            self.hass.config_entries.async_update_entry(
                self.reauth_entry, data=user_input
            )
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        if (controller_data := controller_info.get("gateway")) is None:
            controller_data = controller_info
        controller_type = controller_data["controllerType"]
        LOGGER.debug(
            "Integrating SHC %s with serial number: %s",
            controller_type,
            controller_data["serialNumber"],
        )

        return self.async_create_entry(
            title=f"SHC {controller_type}",
            data={
                **user_input,
            },
        )
