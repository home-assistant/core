"""Config flow for Sunsynk integration."""
from __future__ import annotations

import logging
from typing import Any

from sunsynk.client import InvalidCredentialsException, Inverter, SunsynkClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, STEP_USER

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SunsynkHub:
    """SunsynkHub - authenticates against Sunsynk API."""

    def __init__(self) -> None:
        """Initialise a config flow for Sunsynk."""
        self.client: SunsynkClient | None = None

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        try:
            if self.client is None:
                self.client = await SunsynkClient.create(username, password)
            else:
                self.client.username = username
                self.client.password = password
                self.client = await self.client.login()
            return True
        except InvalidCredentialsException:
            return False

    async def get_inverters(self) -> list[Inverter]:
        """Get the list of inverters."""
        if self.client is None:
            return []
        return await self.client.get_inverters()


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> SunsynkHub:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    if CONF_USERNAME not in data or CONF_PASSWORD not in data:
        raise InvalidAuth

    hub = SunsynkHub()

    if not await hub.authenticate(data[CONF_USERNAME], data[CONF_PASSWORD]):
        raise InvalidAuth

    return hub


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sunsynk."""

    VERSION = 1

    username: str | None = None
    password: str | None = None
    hub: SunsynkHub | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self.hub = await validate_input(self.hass, user_input)
                self.username = user_input[CONF_USERNAME]
                self.password = user_input[CONF_PASSWORD]
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_USERNAME: self.username,
                        CONF_PASSWORD: self.password,
                    },
                )

        return self.async_show_form(
            step_id=STEP_USER, data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
