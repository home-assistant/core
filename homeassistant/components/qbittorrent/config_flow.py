"""Config flow for qBittorrent."""
import logging
from typing import Any

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.data_entry_flow import FlowResult

from .const import DEFAULT_NAME, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def validate_input(data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect."""
    client = Client(data[CONF_URL], verify=data[CONF_VERIFY_SSL])
    client.login(data[CONF_USERNAME], data[CONF_PASSWORD])
    client.get_alternative_speed_status()  # Get an arbitrary attribute that requires authentication


class QbittorrentConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for the qBittorrent integration."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a user-initiated config flow."""
        errors = {}

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(validate_input, user_input)
            except LoginRequired:
                errors = {"base": "invalid_auth"}
            except RequestException:
                errors = {"base": "cannot_connect"}
            if not errors:
                await self.async_set_unique_id(user_input.get(CONF_NAME))
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME), data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_URL, default=DEFAULT_URL): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )
