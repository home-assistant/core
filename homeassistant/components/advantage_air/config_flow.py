"""Config Flow for Advantage Air integration."""
import logging

from advantage_air import advantage_air
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.core import callback

from .const import ADVANTAGE_AIR_RETRY, DOMAIN

ADVANTAGE_AIR_DEFAULT_PORT = 2025

ADVANTAGE_AIR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Optional(CONF_PORT, default=ADVANTAGE_AIR_DEFAULT_PORT): int,
    }
)

_LOGGER = logging.getLogger(__name__)


class AdvantageAirConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Advantage Air API connection."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input):
        """Get configuration from the user."""
        if not user_input:
            return self._show_form()

        ip_address = user_input.get(CONF_IP_ADDRESS)
        port = user_input.get(CONF_PORT)
        api = advantage_air(ip_address, port, ADVANTAGE_AIR_RETRY)

        try:
            data = await api.async_get()
        except Exception:
            return self._show_form({"base": "connection_error"})
        if "aircons" not in data:
            return self._show_form({"base": "data_error"})

        return self.async_create_entry(
            title=data["system"]["name"],
            data=user_input,
        )

    @callback
    def _show_form(self, errors=None):
        """Show the form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=ADVANTAGE_AIR_SCHEMA,
            errors=errors if errors else {},
        )
