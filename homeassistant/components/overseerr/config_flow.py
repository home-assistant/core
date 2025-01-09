"""Config flow for Overseerr."""

from typing import Any

from python_overseerr import OverseerrClient
from python_overseerr.exceptions import OverseerrError
import voluptuous as vol
from yarl import URL

from homeassistant.components.webhook import async_generate_id
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
    CONF_WEBHOOK_ID,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


class OverseerrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Overseerr config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            url = URL(user_input[CONF_URL])
            if (host := url.host) is None:
                errors[CONF_URL] = "invalid_host"
            else:
                self._async_abort_entries_match({CONF_HOST: host})
                port = url.port
                assert port
                client = OverseerrClient(
                    host,
                    port,
                    user_input[CONF_API_KEY],
                    ssl=url.scheme == "https",
                    session=async_get_clientsession(self.hass),
                )
                try:
                    await client.get_request_count()
                except OverseerrError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(
                        title="Overseerr",
                        data={
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_SSL: url.scheme == "https",
                            CONF_API_KEY: user_input[CONF_API_KEY],
                            CONF_WEBHOOK_ID: async_generate_id(),
                        },
                    )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_URL): str, vol.Required(CONF_API_KEY): str}
            ),
            errors=errors,
        )
