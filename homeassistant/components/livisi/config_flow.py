"""Config flow for Livisi Home Assistant."""
from __future__ import annotations

from typing import Any

from aiohttp import ClientConnectorError
from aiolivisi import AioLivisi, errors as livisi_errors
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import CONF_HOST, CONF_PASSWORD, DOMAIN, LOGGER


class LivisiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Livisi Smart Home config flow."""

    def __init__(self) -> None:
        """Create the configuration file."""
        self.aio_livisi: AioLivisi = None
        self.data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=self.data_schema)

        errors = {}
        try:
            await self._login(user_input)
        except livisi_errors.WrongCredentialException:
            errors["base"] = "wrong_password"
        except livisi_errors.ShcUnreachableException:
            errors["base"] = "shc_unreachable"
        except livisi_errors.IncorrectIpAddressException:
            errors["base"] = "wrong_ip_address"
        else:
            controller_info: dict[str, Any] = {}
            try:
                controller_info = await self.get_controller()
            except ClientConnectorError:
                errors["base"] = "shc_unreachable"
            if controller_info:
                return await self.create_entity(user_input, controller_info)
            errors["base"] = "shc_unreachable"

        return self.async_show_form(
            step_id="user", data_schema=self.data_schema, errors=errors
        )

    async def _login(self, user_input: dict[str, str]) -> None:
        """Login into Livisi Smart Home."""
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        self.aio_livisi = AioLivisi(web_session)
        livisi_connection_data = {
            "ip_address": user_input[CONF_HOST],
            "password": user_input[CONF_PASSWORD],
        }

        await self.aio_livisi.async_set_token(livisi_connection_data)

    async def create_entity(
        self, user_input: dict[str, str], controller_info: dict[str, Any]
    ) -> FlowResult:
        """Create LIVISI entity."""
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

    async def get_controller(self) -> dict[str, Any]:
        """Return the LIVISI controller data."""
        return await self.aio_livisi.async_get_controller()
