"""Config flow for Overseerr."""

from typing import Any

from python_overseerr import OverseerrClient
from python_overseerr.exceptions import OverseerrError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_URL
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
            self._async_abort_entries_match({CONF_URL: user_input[CONF_URL]})
            session = async_get_clientsession(self.hass)
            client = OverseerrClient(
                user_input[CONF_URL], user_input[CONF_API_KEY], session=session
            )
            try:
                await client.get_request_count()
            except OverseerrError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Overseerr",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_URL): str, vol.Required(CONF_API_KEY): str}
            ),
            errors=errors,
        )
