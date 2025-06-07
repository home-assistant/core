"""Config flow for Laith Switch integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""


class PlaceholderHub:
    """Mockable hub class for the config flow tests."""

    def __init__(self, host: str, username: str, password: str) -> None:
        """Initialize the hub with host, username, and password."""
        self.host = host
        self.username = username
        self.password = password

    async def authenticate(self) -> bool:
        """Simulate checking credentials."""
        if self.username == "invalid":
            raise InvalidAuth
        if self.host == "0.0.0.0":
            raise CannotConnect
        return True


class LaithSwitchConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Laith Switch."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            hub = PlaceholderHub(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )

            try:
                await hub.authenticate()
            except CannotConnect:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_schema(),
                    errors={"base": "cannot_connect"},
                )
            except InvalidAuth:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._get_schema(),
                    errors={"base": "invalid_auth"},
                )

            return self.async_create_entry(title="Name of the device", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema(),
        )

    def _get_schema(self) -> vol.Schema:
        """Return the config flow schema."""
        return vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
