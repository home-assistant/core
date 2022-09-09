"""Config flow for Livisi Home Assistant."""
from __future__ import annotations

from typing import Any

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
        self.host: str | None
        self._info: dict[str, Any] = {}
        self._device_info: dict[str, Any] = {}
        self._auth_headers: dict[str, Any] = {}
        self._aio_livisi: AioLivisi = None
        self._access_data = None
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
        errors: dict[str, str] = {}
        if user_input is not None:
            ip_password: dict[str, str] = user_input
            try:
                await self._login(ip_password)
                return await self.create_entity(ip_password)
            except livisi_errors.WrongCredentialException:
                errors["base"] = "wrong_password"
            except livisi_errors.ShcUnreachableException:
                errors["base"] = "shc_unreachable"
            except livisi_errors.IncorrectIpAddressException:
                errors["base"] = "wrong_ip_address"

        return self.async_show_form(
            step_id="user", data_schema=self.data_schema, errors=errors
        )

    async def _login(self, user_input: dict[str, str]) -> None:
        """Login into Livisi Smart Home."""
        self.host = user_input.get(CONF_HOST)
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        self._aio_livisi = AioLivisi(web_session)
        livisi_connection_data = {
            "ip_address": self.host,
            "password": user_input.get(CONF_PASSWORD),
        }

        await self._aio_livisi.async_set_token(livisi_connection_data)

    async def create_entity(self, user_input: dict[str, str]) -> FlowResult:
        """Create LIVISI entity."""
        controller_info = await self._aio_livisi.async_get_controller()

        if (controller_data := controller_info.get("gateway")) is None:
            controller_data = controller_info
        controller_type = controller_data.get("controllerType")
        LOGGER.debug(
            "Integrating SHC %s with serial number: %s",
            controller_type,
            controller_data.get("serialNumber"),
        )

        return self.async_create_entry(
            title=f"SHC {controller_type}",
            data={
                **user_input,
                CONF_HOST: self.host,
                "os_version": controller_info.get("osVersion"),
                "config_version": controller_info.get("configVersion"),
            },
        )
