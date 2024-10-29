"""The config_flow for Portainer API integration."""

from typing import Any

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectionError
from aiotainer.auth import AbstractAuth
from aiotainer.client import PortainerClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default="9443"): cv.port,
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


class PortainerFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Portainer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[Any, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            _user_input = user_input

            class AsyncTokenAuth(AbstractAuth):
                """Provide aiotainer authentication tied to an OAuth2 based config entry."""

                def __init__(
                    self,
                    websession: ClientSession,
                ) -> None:
                    """Initialize aiotainer auth."""
                    super().__init__(
                        websession,
                        _user_input[CONF_HOST],
                        _user_input[CONF_PORT],
                    )

                async def async_get_access_token(self) -> str:
                    """Return a valid access token."""
                    return _user_input[CONF_ACCESS_TOKEN]

            websession = async_get_clientsession(self.hass, user_input[CONF_VERIFY_SSL])
            api = PortainerClient(AsyncTokenAuth(websession))
            try:
                await api.get_status()
            except (TimeoutError, ClientConnectionError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
