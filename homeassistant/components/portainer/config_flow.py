"""The config_flow for Portainer API integration."""

from typing import Any

import logging

from aiotainer.client import PortainerClient
from aiohttp import ClientResponseError
from aiotainer.auth import AbstractAuth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow
from aiohttp import ClientSession
from . import api
from .coordinator import AutomowerDataUpdateCoordinator
from aiohttp.client_exceptions import ClientConnectionError
from aiotainer.client import PortainerClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DEFAULT_PORT, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT): cv.port,
    }
)


class APsystemsLocalAPIFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Apsystems local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:

            class AsyncTokenAuth(AbstractAuth):
                """Provide aiotainer authentication tied to an OAuth2 based config entry."""

                def __init__(
                    self,
                    websession: ClientSession,
                ) -> None:
                    """Initialize aiotainer auth."""
                    super().__init__(websession, user_input[CONF_IP_ADDRESS])

                async def async_get_access_token(self) -> str:
                    """Return a valid access token."""
                    return user_input[CONF_ACCESS_TOKEN]

            websession = async_get_clientsession(self.hass, False)
            api = PortainerClient(AsyncTokenAuth(websession))
            try:
                device_info = await api.get_status()
            except (TimeoutError, ClientConnectionError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_IP_ADDRESS],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
