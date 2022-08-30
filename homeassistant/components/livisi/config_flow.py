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
        self._host: str = ""
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
            try:
                ip_password: dict[str, str] = user_input
                return await self.async_step_credentials(ip_password)
            except livisi_errors.WrongCredentialException:
                errors["base"] = "wrong_password"
            except livisi_errors.ShcUnreachableException:
                errors["base"] = "shc_unreachable"
            except livisi_errors.IncorrectIpAddressException:
                errors["base"] = "wrong_ip_address"

        return self.async_show_form(
            step_id="credentials", data_schema=self.data_schema, errors=errors
        )

    async def async_step_credentials(self, user_input: dict[str, str]) -> FlowResult:
        """Handle the login step."""
        return await self._login(user_input)

    async def _login(self, user_input: dict[str, str]) -> FlowResult:
        """Login into Livisi Smart Home and register the controller."""
        self._host = str(user_input.get(CONF_HOST))
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        self._aio_livisi = AioLivisi(web_session)
        livisi_connection_data = {
            "ip_address": self._host,
            "password": user_input.get(CONF_PASSWORD),
        }

        await self._aio_livisi.async_set_token(livisi_connection_data)

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
                CONF_HOST: self._host,
                "os_version": controller_info.get("osVersion"),
                "config_version": controller_info.get("configVersion"),
            },
        )
