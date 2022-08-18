"""Config flow for Livisi Home Assistant."""

from typing import Any, Final

from aiolivisi import AioLivisi, errors
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import CONF_HOST, CONF_PASSWORD, DOMAIN, LOGGER

HOST_SCHEMA: Final = vol.Schema({vol.Required(CONF_HOST): str})


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

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            host: str = user_input[CONF_HOST]
            self._host = host
            return await self.async_step_credentials(None)

        return self.async_show_form(step_id="user", data_schema=HOST_SCHEMA)

    async def async_step_credentials(
        self, user_input: dict[str, Any] = None
    ) -> FlowResult:
        """Handle the credentials step."""
        found_errors: dict[str, str] = {}
        if user_input is not None:
            try:
                return await self._login(user_input)
            except errors.WrongCredentialException:
                found_errors["base"] = "wrong_password"
            except errors.ShcUnreachableException:
                found_errors["base"] = "shc_unreachable"
            except errors.IncorrectIpAddressException:
                found_errors["base"] = "wrong_ip_address"
        else:
            user_input = {}

        schema = vol.Schema(
            {
                vol.Required(CONF_PASSWORD, default=user_input.get(CONF_PASSWORD)): str,
            }
        )

        return self.async_show_form(
            step_id="credentials", data_schema=schema, errors=found_errors
        )

    async def _login(self, user_input: dict[str, Any]):
        """Login into Livisi Smart Home and register the controller."""
        web_session = aiohttp_client.async_get_clientsession(self.hass)
        self._aio_livisi = AioLivisi.get_instance()
        self._aio_livisi.web_session = web_session
        livisi_connection_data = {
            "ip_address": self._host,
            "password": user_input.get(CONF_PASSWORD),
        }

        await self._aio_livisi.async_set_token(livisi_connection_data)

        controller_info = await self._aio_livisi.async_get_controller()

        if controller_info.get("gateway") is not None:
            controller_data = controller_info.get("gateway")
        else:
            controller_data = controller_info
        controller_type = controller_data.get("controllerType")
        LOGGER.info(
            "Integrating SHC %s with serial number: %s",
            controller_type,
            controller_data.get("serialNumber"),
        )

        return self.async_create_entry(
            title=f"SHC {controller_type}",
            data={
                **user_input,
                CONF_HOST: self._host,
                "osVersion": controller_info.get("osVersion"),
                "configVersion": controller_info.get("configVersion"),
            },
        )
