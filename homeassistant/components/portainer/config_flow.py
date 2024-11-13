"""The config_flow for Portainer API integration."""

from typing import Any

from aiohttp.client_exceptions import ClientConnectionError
from aiotainer.client import PortainerClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import AsyncConfigEntryAuth
from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): cv.string,
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
            websession = async_get_clientsession(self.hass, user_input[CONF_VERIFY_SSL])
            api = PortainerClient(AsyncConfigEntryAuth(websession, user_input))
            try:
                await api.get_status()
            except (TimeoutError, ClientConnectionError):
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_URL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_URL],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
